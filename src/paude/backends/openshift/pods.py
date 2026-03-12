"""Pod readiness checking and status operations."""

from __future__ import annotations

import os
import sys
import time

from paude.backends.openshift.exceptions import PodNotReadyError
from paude.backends.openshift.oc import OcClient

# Terminal failure states that indicate immediate failure (no point waiting)
TERMINAL_WAITING_REASONS = frozenset(
    {
        "ImagePullBackOff",
        "ErrImagePull",
        "CrashLoopBackOff",
        "CreateContainerConfigError",
        "InvalidImageName",
        "CreateContainerError",
    }
)


class PodWaiter:
    """Handles pod readiness checking and debug info collection."""

    def __init__(self, oc: OcClient, namespace: str) -> None:
        self._oc = oc
        self._namespace = namespace

    def get_container_status(self, pod_name: str) -> tuple[str | None, str | None]:
        """Get container waiting reason and message from pod status.

        Args:
            pod_name: Name of the pod.

        Returns:
            Tuple of (waiting_reason, waiting_message) or (None, None).
        """
        result = self._oc.run(
            "get",
            "pod",
            pod_name,
            "-n",
            self._namespace,
            "-o",
            "jsonpath={.status.containerStatuses[0].state.waiting.reason},"
            "{.status.containerStatuses[0].state.waiting.message}",
            check=False,
        )

        if result.returncode != 0:
            return None, None

        parts = result.stdout.strip().split(",", 1)
        reason = parts[0] if parts[0] else None
        message = parts[1] if len(parts) > 1 and parts[1] else None
        return reason, message

    def collect_debug_info(self, pod_name: str) -> str:
        """Collect debug information for a failed pod.

        Args:
            pod_name: Name of the pod.

        Returns:
            Formatted debug information string.
        """
        ns = self._namespace
        lines = []

        # Get pod events
        events_result = self._oc.run(
            "get",
            "events",
            "-n",
            ns,
            "--field-selector",
            f"involvedObject.name={pod_name}",
            "--sort-by=.lastTimestamp",
            "-o",
            "custom-columns=TIME:.lastTimestamp,TYPE:.type,"
            "REASON:.reason,MESSAGE:.message",
            check=False,
        )
        if events_result.returncode == 0 and events_result.stdout.strip():
            lines.append("=== Pod Events ===")
            lines.append(events_result.stdout.strip())

        # Get pod describe (truncated)
        describe_result = self._oc.run(
            "describe",
            "pod",
            pod_name,
            "-n",
            ns,
            check=False,
        )
        if describe_result.returncode == 0 and describe_result.stdout.strip():
            lines.append("\n=== Pod Describe (truncated) ===")
            describe_lines = describe_result.stdout.strip().split("\n")
            lines.append("\n".join(describe_lines[:50]))
            if len(describe_lines) > 50:
                lines.append(f"... ({len(describe_lines) - 50} more lines)")

        # Try to get container logs (may not exist if container never started)
        logs_result = self._oc.run(
            "logs",
            pod_name,
            "-n",
            ns,
            "--tail=30",
            check=False,
        )
        if logs_result.returncode == 0 and logs_result.stdout.strip():
            lines.append("\n=== Container Logs (last 30 lines) ===")
            lines.append(logs_result.stdout.strip())

        return "\n".join(lines) if lines else "No debug information available"

    def wait_for_ready(
        self,
        pod_name: str,
        timeout: int = 300,
    ) -> None:
        """Wait for a pod to be in Running state.

        Args:
            pod_name: Name of the pod.
            timeout: Timeout in seconds. Can be overridden via
                PAUDE_POD_READY_TIMEOUT environment variable.

        Raises:
            PodNotReadyError: If pod is not ready within timeout.
        """
        # Allow environment variable to override timeout
        timeout = int(os.environ.get("PAUDE_POD_READY_TIMEOUT", str(timeout)))

        start_time = time.time()
        ns = self._namespace
        last_status_time = start_time
        progress_interval = 15  # Print status every 15 seconds

        while time.time() - start_time < timeout:
            elapsed = int(time.time() - start_time)
            remaining = timeout - elapsed

            result = self._oc.run(
                "get",
                "pod",
                pod_name,
                "-n",
                ns,
                "-o",
                "jsonpath={.status.phase}",
                check=False,
            )

            phase = result.stdout.strip() if result.returncode == 0 else "Unknown"

            if result.returncode == 0:
                if phase == "Running":
                    return
                elif phase in ("Failed", "Error"):
                    debug_info = self.collect_debug_info(pod_name)
                    print(f"\n{debug_info}", file=sys.stderr)
                    raise PodNotReadyError(f"Pod {pod_name} failed: {phase}")

            # Check for terminal waiting states (e.g., ImagePullBackOff)
            waiting_reason, waiting_message = self.get_container_status(pod_name)
            if waiting_reason in TERMINAL_WAITING_REASONS:
                debug_info = self.collect_debug_info(pod_name)
                print(f"\n{debug_info}", file=sys.stderr)
                if waiting_message:
                    msg = f"{waiting_reason}: {waiting_message}"
                else:
                    msg = waiting_reason
                raise PodNotReadyError(
                    f"Pod {pod_name} failed with terminal error: {msg}"
                )

            # Print progress every 15 seconds
            current_time = time.time()
            if current_time - last_status_time >= progress_interval:
                status_parts = [f"phase={phase}"]
                if waiting_reason:
                    status_parts.append(f"waiting={waiting_reason}")
                status_str = ", ".join(status_parts)
                print(
                    f"  Waiting for pod... ({elapsed}s/{remaining}s, {status_str})",
                    file=sys.stderr,
                )
                last_status_time = current_time

            time.sleep(2)

        # Timeout reached - collect debug info
        debug_info = self.collect_debug_info(pod_name)
        print(f"\n{debug_info}", file=sys.stderr)
        raise PodNotReadyError(f"Pod {pod_name} not ready within {timeout} seconds")

"""
steamvr_gesture.py - SteamVR gesture recognition for VTAuder
"""
import threading
import time
try:
    import openvr
except ImportError:
    openvr = None

class SteamVRGestureRecognizer:
    def __init__(self, gesture_callback):
        self.gesture_callback = gesture_callback
        self.running = False
        self.thread = None
        self.last_positions = {}
        self.gesture_map = {
            'swipe_up': 'Hello!',
            'swipe_down': 'Thank you!',
            'swipe_left': 'Need help!',
            'swipe_right': 'Goodbye!'
        }

    def start(self):
        if openvr is None:
            print("[SteamVR] openvr not installed.")
            return False
        openvr.init(openvr.VRApplication_Other)
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()
        print("[SteamVR] Gesture recognizer started.")
        return True

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        try:
            openvr.shutdown()
        except Exception:
            pass
        print("[SteamVR] Gesture recognizer stopped.")

    def _poll_loop(self):
        import time
        while self.running:
            poses = [openvr.TrackedDevicePose_t() for _ in range(openvr.k_unMaxTrackedDeviceCount)]
            openvr.VRSystem().getDeviceToAbsoluteTrackingPose(
                openvr.TrackingUniverseStanding,
                0,
                poses
            )
            for i in range(openvr.k_unMaxTrackedDeviceCount):
                device_class = openvr.VRSystem().getTrackedDeviceClass(i)
                if device_class == openvr.TrackedDeviceClass_Controller:
                    pose = poses[i]
                    if pose.bPoseIsValid:
                        pos = (
                            pose.mDeviceToAbsoluteTracking[0][3],
                            pose.mDeviceToAbsoluteTracking[1][3],
                            pose.mDeviceToAbsoluteTracking[2][3]
                        )
                        last_pos = self.last_positions.get(i)
                        if last_pos:
                            dx = pos[0] - last_pos[0]
                            dy = pos[1] - last_pos[1]
                            dz = pos[2] - last_pos[2]
                            gesture = self._detect_gesture(dx, dy, dz)
                            if gesture:
                                text = self.gesture_map.get(gesture)
                                print(f"[STEAMVR DEBUG] Detected gesture: {gesture} | Text: {text}")
                                if text:
                                    print(f"[STEAMVR DEBUG] Sending gesture text to callback: {text}")
                                    self.callback(text)
                        self.last_positions[i] = pos
            time.sleep(0.05)

    def _detect_gesture(self, dx, dy, dz):
        # Simple gesture detection based on movement direction
        threshold = 0.15
        if dy > threshold:
            return 'swipe_up'
        elif dy < -threshold:
            return 'swipe_down'
        elif dx > threshold:
            return 'swipe_right'
        elif dx < -threshold:
            return 'swipe_left'
        return None

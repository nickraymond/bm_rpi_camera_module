from bm_serial import BristlemouthSerial
from enum import Enum
import RPi.GPIO as GPIO
import time

RELEASE = False


class QuickRelease:
    class ReleaseState(Enum):
        BEGIN_STATE = 0
        RED_LED_STATE = 1
        YELLOW_LED_STATE = 2
        GREEN_LED_STATE = 3
        RELEASE_STATE = 4

    LED_RED = 21
    LED_GREEN = 16
    LED_YELLOW = 20
    PWM_PIN = 12
    PWM_FREQUENCY = 1000

    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.LED_GREEN, GPIO.OUT)
        GPIO.setup(self.LED_RED, GPIO.OUT)
        GPIO.setup(self.LED_YELLOW, GPIO.OUT)
        GPIO.setup(self.PWM_PIN, GPIO.OUT)
        self.pwm = GPIO.PWM(self.PWM_PIN, self.PWM_FREQUENCY)
        self.state = self.ReleaseState.BEGIN_STATE.value
        self.time = 0

    def process_release(self, release: bool):
        ret = True

        if release:
            if self.state == self.ReleaseState.BEGIN_STATE.value:
                self.time = time.monotonic()
                self.state = self.ReleaseState.RED_LED_STATE.value
                GPIO.output(self.LED_RED, GPIO.HIGH)
                GPIO.output(self.LED_YELLOW, GPIO.LOW)
                GPIO.output(self.LED_GREEN, GPIO.LOW)
            elif self.state == self.ReleaseState.RED_LED_STATE.value:
                if time.monotonic() - self.time >= 3.0:
                    self.state = self.ReleaseState.YELLOW_LED_STATE.value
                    self.time = time.monotonic()
                    GPIO.output(self.LED_RED, GPIO.LOW)
                    GPIO.output(self.LED_YELLOW, GPIO.HIGH)
                    GPIO.output(self.LED_GREEN, GPIO.LOW)
            elif self.state == self.ReleaseState.YELLOW_LED_STATE.value:
                if time.monotonic() - self.time >= 3.0:
                    self.state = self.ReleaseState.GREEN_LED_STATE.value
                    self.time = time.monotonic()
                    GPIO.output(self.LED_RED, GPIO.LOW)
                    GPIO.output(self.LED_YELLOW, GPIO.LOW)
                    GPIO.output(self.LED_GREEN, GPIO.HIGH)
            elif self.state == self.ReleaseState.GREEN_LED_STATE.value:
                if time.monotonic() - self.time >= 3.0:
                    self.state = self.ReleaseState.RELEASE_STATE.value
                    self.time = time.monotonic()
                    GPIO.output(self.LED_RED, GPIO.LOW)
                    GPIO.output(self.LED_YELLOW, GPIO.LOW)
                    GPIO.output(self.LED_GREEN, GPIO.LOW)
                    self.pwm.start(50)
            elif self.state == self.ReleaseState.RELEASE_STATE.value:
                if time.monotonic() - self.time >= 1.0:
                    self.state = self.ReleaseState.BEGIN_STATE.value
                    self.pwm.stop()
                    self.time = 0
                    ret = False

            return ret


def quick_release(node_id, type, version, topic_len, topic, data_len, data):
    global RELEASE
    print("Received subscription on topic: {}".format(topic))
    print("Node ID: {}".format(hex(node_id)))
    print("Type: {}".format(type))
    print("Version: {}".format(version))
    print("Topic: {}".format(topic))
    print("Topic Length: {}".format(topic_len))
    print("Data: {}".format(data))
    print("Data Length: {}".format(data_len))
    if RELEASE is not True:
        RELEASE = True


def main() -> None:
    global RELEASE
    bm = BristlemouthSerial()
    qr = QuickRelease()
    print("starting the quick release application...")
    print("subscribing to quick_release")
    bm.bristlemouth_sub("quick_release", quick_release)

    last_send = time.monotonic()

    while True:
        bm.bristlemouth_process(0.1)
        RELEASE = qr.process_release(RELEASE)
        # Temp, blast network to receive data
        now = time.monotonic()
        if now - last_send > 30:
            last_send = now
            bm.spotter_tx(
                b"sensor1: 1234.56, binary_ok_too: \x00\x01\x02\x03\xff\xfe\xfd"
            )
            bm.spotter_log(
                "any_file_name.log",
                "Sensor 1: 1234.99. More detailed human-readable info for the SD card logs.",
            )


if "__main__":
    main()

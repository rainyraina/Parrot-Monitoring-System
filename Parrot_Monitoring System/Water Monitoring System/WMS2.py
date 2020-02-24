from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import RPi.GPIO as GPIO
import time
from time import sleep
import datetime
import json
import datetime as datetime
from multiprocessing import Process

import string, random

def rand_str_gen(size=20):
    lettersal = ''.join(random.choice(string.ascii_letters) for i in range(size))
    lettersd = ''.join(random.choice(string.digits) for i in range(size))
    lettersp = ''.join(random.choice(string.punctuation) for i in range(size))
    letter = str(lettersal) + str(lettersd) + str(lettersp)
    return ''.join(random.choice(letter) for i in range(size))

#Water pump
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(13,GPIO.OUT)

#MQTT
host = "a1hdsuh2fiycts-ats.iot.us-east-1.amazonaws.com"
rootCAPath = "WMS/AmazonRootCA1.pem"
certificatePath = "WMS/certificate.pem.crt"
privateKeyPath = "WMS/private.pem.key"


def customCallback(client, userdata, message):
	payload = json.loads(message.payload)
	if payload["DeviceID"] == "WMS1":
		refillduration=float(payload["refill"])
		refill(refillduration)


def subscribe():
    my_rpi = AWSIoTMQTTClient("basicPubSub" + rand_str_gen())
    my_rpi.configureEndpoint(host, 8883)
    my_rpi.configureCredentials(rootCAPath, privateKeyPath, certificatePath)
    my_rpi.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
    my_rpi.configureDrainingFrequency(2)  # Draining: 2 Hz
    my_rpi.configureConnectDisconnectTimeout(10)  # 10 sec
    my_rpi.configureMQTTOperationTimeout(5)  # 5 sec
    my_rpi.connect()
    my_rpi.subscribe("monitor/WMS/refill", 1, customCallback)
    while True:
        print("Waiting for call...")
        sleep(5)
		
def refill(refillduration):
	GPIO.output(13, 0)
	print("Start")
	sleep(refillduration)
	GPIO.output(13, 1)
	print("Stop")
	sleep(1)
	print("Refilling for: "+ str(refillduration))
	return ("water refilled")
	
		


if __name__ == '__main__':
    subscribe_proc = Process(name='subscribe', target=subscribe)
    subscribe_proc.start()
    subscribe_proc.join()
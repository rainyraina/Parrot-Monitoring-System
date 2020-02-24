import Adafruit_DHT
from gpiozero import MotionSensor
import RPi.GPIO as GPIO
import picamera
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import json
import threading
import datetime as datetime
from time import sleep
import time
import boto3
import botocore
import requests

#Motion Sensor
pir = MotionSensor(17, sample_rate=5,queue_len=1)
lastsent = time.time()

#Food Feeder
GPIO.setup(18,GPIO.OUT)

#S3 Bucket
BUCKET = 'arn:aws:s3:::uploaded-images-for-rekognition' # replace with your own unique bucket name
location = {'LocationConstraint': 'us-east-1'}


#MQTT
host = "a23gkxvm8h23di-ats.iot.us-east-1.amazonaws.com"
rootCAPath = ""
certificatePath = ""
privateKeyPath = ""

#Telegram
bot_token = ''
bot_chatID = ''


my_rpi = AWSIoTMQTTClient("basicPubSub")
my_rpi.configureEndpoint(host, 8883)
my_rpi.configureCredentials(rootCAPath, privateKeyPath, certificatePath)

my_rpi.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
my_rpi.configureDrainingFrequency(2)  # Draining: 2 Hz
my_rpi.configureConnectDisconnectTimeout(10)  # 10 sec
my_rpi.configureMQTTOperationTimeout(5)  # 5 sec

# Connect and subscribe to AWS IoT
my_rpi.connect()

def publishmqtt(Temperature,Humidity):
	message = {}
	message["DeviceID"] = "FMS1"
	now = datetime.datetime.now()
	message["datetime"] = now.isoformat()      
	message["AT"] = Humidity
	message["AH"] = Temperature
	my_rpi.publish("monitor/FMS/sensor", json.dumps(message), 1)
		
def tempandhum():
	temperature, humidity = Adafruit_DHT.read_retry(11, 27)
	publishmqtt(temperature ,humidity)
	return(temperature, humidity)
	
	
def motiondetected():
	timestring = time.strftime("%Y-%m-%d_%H_%M_%S", time.localtime())
	print ("Bird detected at food Bowl at: " +timestring + "\nTaking photo...")
	photo = "/home/pi/Desktop/photo/photo_"+timestring+".jpg"
	filename="FMS1_"+timestring+".jpg"
	with picamera.PiCamera() as camera:
		camera.capture(photo)
		print("photo taken")
		uploadToS3(filename,photo)
	

def uploadToS3(filename,full_path):
    s3 = boto3.resource('s3') # Create an S3 resource
    exists = True

    try:
        s3.meta.client.head_bucket(Bucket="uploaded-images-for-rekognition")
    except botocore.exceptions.ClientError as e:
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            exists = False

    if exists == False:
        s3.create_bucket(Bucket="uploaded-images-for-rekognition" ,CreateBucketConfiguration={'LocationConstraint': 'us-east-1'})
    
    # Upload the file
    s3.Object("uploaded-images-for-rekognition", filename).put(Body=open(full_path, 'rb'))
    print("File uploaded")

def send(bot_message): 
	print("Sending Telegram Message")
	send_text = 'https://api.telegram.org/bot' + bot_token + '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&text=' + bot_message
	try:
		response = requests.get(send_text)
		return response.json()
	except:
		print("Unable to send to Telegram") 
	else:
		print("Message sent 5 minutes ago")

	
while True:
	temperature, humidity = tempandhum()
	print("Temperature:" + str(temperature))
	print("Humidity:" + str(humidity))
	noti=[]
	if ((temperature > 45) || (temperature < 18)):
		noti.append("Water temperature undesirable")
	if (humidity < 30):
		noti.append("Humidity too low.")
	if (len(noti) != 0):
		currenttime = time.time()
		difference = currenttime - lastsent
		if (difference > 300): # Will send only every 5 minutes
			lastsent = time.time() #update last sent
			for x in noti:
				send(x)

	if pir.motion_detected:
		currenttime = time.time()
		difference = currenttime - lastsent
		if (difference > 300):
			motiondetected()
			lastsent = time.time()
		else:
			print("photo already taken!")
			
	sleep(15)	
		

	
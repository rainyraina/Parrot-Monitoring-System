import serial
import time
from time import sleep
import datetime
import picamera
import Adafruit_DHT
from gpiozero import MotionSensor
import RPi.GPIO as GPIO
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import json
import datetime as datetime
import boto3
import botocore
import requests

# Water Level Sensor
TRIG = 23 
ECHO = 24
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(TRIG,GPIO.OUT)
GPIO.setup(ECHO,GPIO.IN)

#Motion Sensor
pir = MotionSensor(17, sample_rate=5,queue_len=1)
lastsent = time.time()

#Water Temp and TDS
ser = serial.Serial('/dev/ttyUSB0',9600)

#MQTT
host = "a1hdsuh2fiycts-ats.iot.us-east-1.amazonaws.com"
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
my_rpi.configureConnectDisconnectTimeout(20)  # 10 sec
my_rpi.configureMQTTOperationTimeout(20)  # 5 sec
my_rpi.connect()

def publishmqtt(watertemp,tds,waterlevel):
	message = {}
	message["DeviceID"] = "WMS1"
	now = datetime.datetime.now()
	message["datetime"] = now.isoformat()      
	message["WaterTemp"] = watertemp
	message["TDS"] = tds
	message["WaterLevel"] = waterlevel
	my_rpi.publish("monitor/WMS/sensor", json.dumps(message), 1)
		
def motiondetected():
	timestring = time.strftime("%Y-%m-%d_%H_%M_%S", time.localtime())
	print ("Bird detected at water Bowl at: " +timestring + "\nTaking photo...")
	photo = "/home/pi/Desktop/photo/photo_"+timestring+".jpg"
	filename="WMS1_"+timestring+".jpg"
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
		
def checkwaterlevel():
	GPIO.output(TRIG, False)
	GPIO.output(TRIG, True)
	time.sleep(0.00001)
	GPIO.output(TRIG, False)
	pulse_start = 0 
	pulse_end   = 0
	while GPIO.input(ECHO)==0:
		pulse_start = time.time()
	while GPIO.input(ECHO)==1:
		pulse_end = time.time()
	pulse_duration = pulse_end - pulse_start #time difference between start and end
	dist = (pulse_duration * 1280)/2

	#To find the water level
	distance = 6.6 - dist
	
	if distance > 0:
		#print("Water Level: " + str("%.2f" % round(distance,2)))
		height=(float("%.2f" % round(distance,2)))
		return(height)
	else:
		height = 0
		return(height)

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
	read_serial=ser.readline()
	data = read_serial.split()
	Temp = data[0]
	TDS = data[1]
	print("Temp: "+Temp+"C")
	print("TDS: " + TDS)
	waterlevel=checkwaterlevel()
	print(waterlevel)
	publishmqtt(Temp,TDS,str(waterlevel))
	noti=[]
	if (Temp > 45 || Temp < 18):
		noti.append("Water temperature undesirable")
	if (TDS > 600):
		noti.append("TDS more than 600")
	if (waterlevel < 3):
		noti.append("Need to refill water bowl")
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
		


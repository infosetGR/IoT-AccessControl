from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from picamera import PiCamera
import argparse
import boto3
import time
import os
import json


#Speak text with AWS 
def Speak(audiotext, client):

    afile='sounds-var2/'+audiotext.replace(' ','').replace(',','')
    #synthesize common text once
    if not os.path.isfile(afile):
         voice='Emma'
         response = client.synthesize_speech(OutputFormat='mp3', Text=" "+audiotext+" ", VoiceId=voice)    
         thebytes = response['AudioStream'].read()
         thefile = open(afile, 'wb')
         thefile.write(thebytes)
         thefile.close()
    # Play mp3 file via speaker
    print(audiotext)
    # omxplayer_silent is a copy of omxplayer with modified line LD_LIBRARY_PATH="$OMXPLAYER_LIBS${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" $OMXPLAYER_BIN "$@" > /dev/null 2>&1
    os.system('omxplayer_silent {}'.format(afile))


#capture photo using pi camera
def takePhoto(directoryname,name,camera):
        os.system('omxplayer_silent {}'.format("sounds/camera.mp3"))
        dirname = os.path.dirname(__file__)
        directory = os.path.join(dirname, directoryname)
        image = '{0}/{1}.jpg'.format(directory, name)
        print(image)
        # time.sleep(0.1)
        try:
            camera.capture(image)
        except BaseException as e:
            print(e.message)
        print('Your image was saved to '+ image)
        return image
    

#initialize reckognition sdk
def RegisterImageToRekognition(im,name,collection,client):
 
    try:
        response = client.describe_collection(
            CollectionId=collection
        )
        print(response)
    except Exception:
        print(Exception)
        client.create_collection(
            CollectionId=collection
        )

  
        # print(response)

# Get key from RFID uid
def GetNameFromRFID(uid):
    #print([hex(i) for i in uid],[i for i in uid])
    return "-".join(str(n) for n in uid)

# Get data of interest from rekognition response
def processRekognitionJSON(data):
    # with open(file_json) as data_file:    
        # data = json.load(data_file)

    age_range_low=data["FaceDetails"][0]["AgeRange"]["Low"]
    age_range_high=data["FaceDetails"][0]["AgeRange"]["High"]
    gender=data["FaceDetails"][0]["Gender"]["Value"]

	# Sort; and find the highest confidence emotion
    json_obj = data["FaceDetails"][0]
    sorted_obj = sorted(json_obj['Emotions'], key=lambda x : x['Confidence'], reverse=True)
    emotion = sorted_obj[0]['Type']

    return gender, emotion, age_range_low,age_range_high


# used when receiving message from MQTT
def customCallback(client, userdata, message):
    print("Received a new message: ")
    print(message.payload)
    print("from topic: ")
    print(message.topic)
    print("--------------\n\n")

# to publish message to MQTT
def publishMQTT(client,topic,seq,m):
    message = {}
    message['message'] = m
    message['sequence'] = seq
    messageJson = json.dumps(message)
    client.publish(topic, messageJson, 1)

# Configure and subscribe to AWS MQTT
def ConfigureAndSubscribeMQTT():
    rootCAPath = '/home/pi/raspberrypi/aws/root-CA.crt'
    certificatePath ='/home/pi/raspberrypi/aws/RPI3A.cert.pem' 
    privateKeyPath = '/home/pi/raspberrypi/aws/RPI3A.private.key'
    useWebsocket = False
    port = 8883
    host='a1y2f8enewhy8u-ats.iot.us-east-1.amazonaws.com'
    clientId = 'basicPubSub'
    topic = 'sdk/test/Python'
    # Init AWSIoTMQTTClient
    myAWSIoTMQTTClient = None
    myAWSIoTMQTTClient = AWSIoTMQTTClient(clientId)
    myAWSIoTMQTTClient.configureEndpoint(host, port)
    myAWSIoTMQTTClient.configureCredentials(rootCAPath, privateKeyPath, certificatePath)
    # AWSIoTMQTTClient connection configuration
    myAWSIoTMQTTClient.configureAutoReconnectBackoffTime(1, 32, 20)
    myAWSIoTMQTTClient.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
    myAWSIoTMQTTClient.configureDrainingFrequency(2)  # Draining: 2 Hz
    myAWSIoTMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
    myAWSIoTMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec
    # Connect and subscribe to AWS IoT
    myAWSIoTMQTTClient.connect()
    myAWSIoTMQTTClient.subscribe(topic, 1, customCallback)
    return myAWSIoTMQTTClient, topic
    time.sleep(2)

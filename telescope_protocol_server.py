import socket, os, signal
from datetime import datetime, date, timedelta
import re
import requests
import json

API_URL = "https://api.nasa.gov/planetary/apod?api_key=TgLGqLIjepX9U4s5HQHots13dt2TCoDGElpE1Gzd"
DEFAULT_IMG_URL = "https://apod.nasa.gov/apod/image/9904/surv3_apollo12_big.jpg"
ENCODED_HASH = '#'.encode('us-ascii')
class ImgParams:
    def __init__(self):
        self.imgEnd = None
        self.imgStart = None
        self.imgSent = False
        self.imgQty = None


imgParams = ImgParams()

def main():
    sListen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sListen.bind(('', 6002))
    sListen.listen(5)
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)

    while True:
        dialog, dir_cli = sListen.accept()
        print("conexion establecida")
        if os.fork():
            dialog.close()
        else:
            sListen.close()
            attendClient(dialog)
            exit(0)


def attendClient(sDialog):
    crlf = "\r\n".encode('us-ascii')
    msg = "".encode('us-ascii')
    while True:
        buf = sDialog.recv(1024)
        if not buf:
            break
        msg += buf
        while crlf in msg:
            msgSplit = msg.split(crlf)
            print(msg)
            attendRequest(sDialog, msgSplit[0].decode('us-ascii'))
            msg = crlf.join(
                msgSplit[1:]) if len(msgSplit) > 1 else "".encode('us-ascii')
    sDialog.close()


def attendRequest(sDialog, request):
    command = request[:3]
    parameters = request[3:]
    if command == 'DIR':  #Y = (X-A)/(B-A) * (D-C) + C mapping de los valores del rango (a,b) a (c,d)
        dirParam = request[3:15]
        attendDir(sDialog, dirParam)
    elif command == 'TME':  #Jun 16, 1995 hasta hoy
        pass
    elif command == 'IMG':
        toSend = attendIMG(sDialog,parameters) #DONE
    elif command == 'QTY':
        #Peti a la api
        if not imgParams.imgSent:
            sendError(sDialog, 1)  #not previous query for IMG
        elif not parameters:
            sendError(sDialog, 4)  #no parameters

        elif not re.match('^\d+$', parameters):
            sendError(sDialog, 5)  #format error

        elif (int(parameters) < 0 and int(parameters) > imgParams.imgQty):
            sendError(sDialog, 10)
        else:
            images = b''
            for i in range(int(parameters)):
                #Solamente el hash entre el tamaño y la imagen porque ya se sabe lo que mide el campo de la imagen 
                image = apiRequest(imgParams.imgStart)
                images += str(len(image)).encode('us-ascii') + ENCODED_HASH + image 
                imgParams.imgStart += timedelta(days=1)
            sDialog.sendall("OK".encode('us-ascii') + images)
    else:
        #COMMAND NOT FOUND ERR-2
        sendError(sDialog, 2)


def sendImages(qty):
    pass
    #si todo correcto
    


def attendDir(sDialog, dirParam):
    #Comprobar tamano
    if (len(dirParam)!=11):
        sendError(sDialog,5)
    declination = dirParam[:5]  #5 digitos
    ascension = dirParam[5:]  #6 digitos
    if re.match('^[+-]\d{4}', declination) and re.match('^/d{6}', ascension):
        numDec = float(declination[1:3] + '.' + declination[3:])
        if numDec<0 and numDec>90:
            sendError(sDialog, 5)
        try:
            hour = datetime.strptime(ascension,'%H%M%S')
        except ValueError:
            sendError(sDialog, 5)
    else:
        #ERROR
        sendError(sDialog, 5)


def attendIMG(sDialog, parameters):
    value = re.match('^(\d{14})$|^(\d{28})$', parameters)
    if value:
        value = value.group(0)
        try:
            date1 = datetime.strptime(value[:14], '%Y%m%d%H%M%S')
            qty = 1
            imgParams.imgStart = date1
            toSend = b''
            if (len(value) == 28):
                date2 = datetime.strptime(value[14:], '%Y%m%d%H%M%S')
                deltaDate = date1 - date2
                qty = abs(deltaDate.days)+1
                imgParams.imgStart,imgParams.imgEnd = (date1,date2) if deltaDate.total_seconds() < 0 else (date2,date1)
                imgParams.imgQty = qty
                imgParams.imgSent = True
                toSend = f'OK{imgParams.imgQty}\r\n'.encode('us-ascii')
            else:
                img = apiRequest(date1)
                toSend = "OK".encode('us-ascii') + str(len(img)).encode('us-ascii') + ENCODED_HASH + img + "\r\n".encode('us-ascii')
            sDialog.sendall(toSend)
            print("enviado")
        except ValueError:
            print("Te envio un error")
            #ERROR DE FORMATO
            sendError(sDialog, 5)
    else:
        if parameters:
            sendError(sDialog,5)
        else:
            sendError(sDialog,4)

def sendError(sDialog, errorNum):
    print("Ha llegado al error")
    sDialog.sendall(f"ER{errorNum}\r\n".encode('us-ascii')) 

def apiRequest(photoDate):
    response = requests.get(f"{API_URL}&date={imgParams.imgStart.strftime('%Y-%m-%d')}")
    if(response.status_code == 200):
        try:
            info = json.loads(response.text)
            print(info)
            if(info["media_type"] == "image"):
                print(info["url"])
                response = requests.get(info["url"])
            else:
                sendError(9)
        except ValueError:
            sendError(9)
        img = b''
        for chunk in response.iter_content():
            img += chunk
    return img

main()
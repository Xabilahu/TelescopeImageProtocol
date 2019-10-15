import socket, os, signal, re, requests, json
from datetime import datetime, date, timedelta

API_URL = "https://api.nasa.gov/planetary/apod?api_key=TgLGqLIjepX9U4s5HQHots13dt2TCoDGElpE1Gzd"
DEFAULT_IMG_URL = "https://apod.nasa.gov/apod/image/9904/surv3_apollo12_big.jpg"
ENCODED_HASH = '#'.encode('us-ascii')
MIN_DATE = datetime.strptime("19950615000000", "%Y%m%d%H%M%S")

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
    toSend = b''
    if command == 'DIR':  #Y = (X-A)/(B-A) * (D-C) + C mapping de los valores del rango (a,b) a (c,d)
        toSend = attendDIR(parameters)
    elif command == 'TME':
        toSend = attendTME(parameters)
    elif command == 'IMG':
        toSend = attendIMG(parameters) #DONE
    elif command == 'QTY':
        toSend = attendQTY(parameters)
    else:
        #COMMAND NOT FOUND ERR-2
        toSend = getError(2)
    sDialog.sendall(toSend)

def getImage(justOneImg):
    #Solamente el hash entre el tamaño y la imagen porque ya se sabe lo que mide el campo de la imagen 
    image = apiRequest(imgParams.imgStart, justOneImg)
    imgParams.imgStart += timedelta(days=1)
    return str(len(image)).encode('us-ascii') + ENCODED_HASH + image 
    
def attendDIR(parameters):
    toSend = b''
    #Comprobar tamano
    if (len(parameters)!=11):
        toSend = getError(5)
    else :
        declination = parameters[:5]  #5 digitos
        ascension = parameters[5:]  #6 digitos
        if re.match('[+-]\d{4}', declination) and re.match('/d{6}', ascension):
            numDec = float(declination[1:3] + '.' + declination[3:])
            if numDec < 0 and numDec > 90:
                toSend = getError(5)
            else:
                toSend = mapDirToDate(declination, ascension)
        else:
            #ERROR
            toSend = getError(5)
    return toSend

def attendIMG(parameters):
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
                img = apiRequest(date1, True)
                toSend = "OK".encode('us-ascii') + str(len(img)).encode('us-ascii') + ENCODED_HASH + img
        except ValueError:
            #ERROR DE FORMATO
            toSend = getError(5)
    else:
        if parameters:
            toSend = getError(5)
        else:
            toSend = getError(4)
    return toSend

def attendQTY(parameters):
     #Peti a la api
    if not imgParams.imgSent:
        toSend = getError(1)  #not previous query for IMG
    elif not parameters:
        toSend = getError(4)  #no parameters
    elif not re.match('^\d+$', parameters):
        toSend = getError(5)  #format error
    elif (int(parameters) < 0 and int(parameters) > imgParams.imgQty):
        toSend = getError(10)
    else:
        toSend += "OK".encode('us-ascii')
        justOneImg = True if (int(parameters) == 1) else False
        for i in range(int(parameters)):
            toSend += getImage(justOneImg)
        if justOneImg:
            toSend += "\r\n".encode('us-ascii')
    return toSend

def attendTME(parameters):
    return 'WORK IN PROGRESS'.encode('us-ascii')

def getError(errorNum):
    return f"ER{errorNum}\r\n".encode('us-ascii') 

def apiRequest(photoDate, justOneImg):
    toSend = b''
    deltaSeconds = (photoDate - MIN_DATE).total_seconds()
    if deltaSeconds >= 0:
        response = requests.get(f"{API_URL}&date={imgParams.imgStart.strftime('%Y-%m-%d')}")
        if(response.status_code == 200):
            try:
                info = json.loads(response.text)
                if(info["media_type"] == "image"):
                    response = requests.get(info["url"])
                    for chunk in response.iter_content():
                        toSend += chunk
                else:
                    if justOneImg:
                        toSend = getError(9)
                    else:
                        toSend = getError(11)
            except ValueError:
                if justOneImg:
                    toSend = getError(9)
                else:
                    toSend = getError(11)
    else:
        if justOneImg:
            toSend = getError(8)
        else:
            toSend = getError(11)
    return toSend

def mapDirToDate(declination, ascension):
    try:
        requestedHours = datetime.strptime(ascension,'%H%M%S')
        dayPool = (datetime.now() - MIN_DATE).days
        requestedDays = ((float(declination[:3] + '.' + declination[3:])) + 90) / 180 * dayPool
        requestedDate = MIN_DATE + timedelta(days=requestedDays, hours=requestedHours.hour, minutes=requestedHours.minute, seconds=requestedHours.minute)
        toSend = datetime.strftime(requestedDate, "OK%Y%m%d%H%M%S\r\n").encode('us-ascii')
    except ValueError:
        toSend = getError(5)
    return toSend

def mapDateToDir(date):
    try:
        requestedDate = datetime.strptime(date, "%Y%m%d%H%M%S")
        deltaSeconds = (requestedDate - MIN_DATE).total_seconds()
        if deltaSeconds < 0 or requestedDate > datetime.now():
            toSend = getError(7)
        else:
            ascension = date[8:]
            requestedDays = (requestedDate - MIN_DATE).days
            maxDays = (datetime.now() - MIN_DATE).days
            degrees = requestedDays / maxDays * 180 - 90
            declination = ('+' if degrees >= 0 else '') + str(round(degrees,2)).replace('.','')
            if len(declination) < 5:
                declination += '0'
            toSend = declination[:5] + ascension
    except ValueError:
        toSend = getError(5)
    return toSend

main()

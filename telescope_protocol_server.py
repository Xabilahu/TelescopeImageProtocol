#!/usr/bin/env python3
import socket, os, signal, re, requests, json, sys
from datetime import datetime, date, timedelta

API_URL = "https://api.nasa.gov/planetary/apod?api_key=TgLGqLIjepX9U4s5HQHots13dt2TCoDGElpE1Gzd"
CODIFICATION = 'us-ascii'
ENCODED_HASH = '#'.encode(CODIFICATION)
MIN_DATE = datetime.strptime("19950615000000", "%Y%m%d%H%M%S")
PORT = 6002
DEBUG_MODE = False
PREDETERMINED_IMAGE = b''

class ImgParams:
    def __init__(self):
        self.imgEnd = None
        self.imgStart = None
        self.awaitingQTY = False
        self.imgQty = None
        self.posibleZero = False

imgParams = ImgParams()

def main():
    if len(sys.argv) >= 2:
        index = 1
        if "-d" in sys.argv[1]:
            global DEBUG_MODE
            DEBUG_MODE = True
            print('Debug Mode activado\n')
            if len(sys.argv) == 3:
                assignPort(sys.argv[2])
        else:
            assignPort(sys.argv[1])
    
    #Se carga al inicio la imagen predeterminada para que cuando se creen los hijos también la tengan accesible
    print("Descargando imagen predeterminada...")
    global PREDETERMINED_IMAGE
    imgParams.imgStart = datetime.strptime("20190411000000", "%Y%m%d%H%M%S")
    PREDETERMINED_IMAGE = apiRequest(imgParams.imgStart, True, False)
    print("Imagen predeterminada descargada.")
    sListen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sListen.bind(('', PORT))
    sListen.listen(5)
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)

    while True:
        dialog, dir_cli = sListen.accept()
        if os.fork():
            dialog.close()
            if DEBUG_MODE:
                print(f'Conexion establecida con {dir_cli[0]}')
        else:
            sListen.close()
            attendClient(dialog)
            exit(0)

def assignPort(port):
    try:
        global PORT 
        PORT = int(port)
    except ValueError:
        print('\nERROR: Número de puerto incorrecto.\n')
        print('Modo de uso: python3 telescope_protocol_server.py [--debug / -d] [PORT]\n')
        print('En caso de no indicar el número de puerto se asignará el puerto 6002 por defecto.')
        exit(1)

def attendClient(sDialog):
    crlf = "\r\n".encode(CODIFICATION)
    msg = "".encode(CODIFICATION)
    while True:
        buf = sDialog.recv(1024)
        if not buf:
            break
        msg += buf
        while crlf in msg:
            msgSplit = msg.split(crlf)
            try:
                decodedMsg = msgSplit[0].decode(CODIFICATION)
                if DEBUG_MODE:
                    print(f'Mensaje recibido de {sDialog.getsockname()[0]}: {decodedMsg}')
                attendRequest(sDialog, decodedMsg)
            except UnicodeDecodeError:
                sDialog.sendall(getError(5))
            msg = crlf.join(msgSplit[1:]) if len(msgSplit) > 1 else "".encode(CODIFICATION)
    if DEBUG_MODE:
        print(f'Conexion cerrada con {sDialog.getsockname()[0]}')
    sDialog.close()

def attendRequest(sDialog, request):
    command = request[:3]
    parameters = request[3:]
    toSend = b''
    if command == 'DIR': 
        if imgParams.posibleZero:
            imgParams.posibleZero = False
        toSend = attendDIR(parameters)
    elif command == 'TME':
        if imgParams.posibleZero:
            imgParams.posibleZero = False
        toSend = attendTME(parameters)
    elif command == 'IMG':
        if imgParams.posibleZero:
            imgParams.posibleZero = False
        toSend = attendIMG(parameters)
    elif command == 'QTY':
        toSend = attendQTY(parameters)
    else:
        #COMMAND NOT FOUND ERR-2
        toSend = getError(2)
    if DEBUG_MODE:
        print(f'Mensaje a enviar a {sDialog.getsockname()[0]}: {toSend}')
    sDialog.sendall(toSend)

def getImage(justOneImg):
    #Solamente el hash entre el tamaño y la imagen porque ya se sabe lo que mide el campo de la imagen 
    image = apiRequest(imgParams.imgStart, justOneImg, False)
    imgParams.imgStart += timedelta(days=1)
    return str(len(image)).encode(CODIFICATION) + ENCODED_HASH + image 

def attendDIR(parameters):
    toSend = b''
    #Comprobar tamano
    if not parameters:
        toSend = getError(4)
    elif (len(parameters)!=11):
        toSend = getError(5)
    else :
        declination = parameters[:5]  #5 digitos
        ascension = parameters[5:]  #6 digitos
        if re.match('[+-]\d{4}', declination) and re.match('\d{6}', ascension):
            numDec = float(declination[1:3] + '.' + declination[3:])
            if numDec < 0 or numDec > 90:
                toSend = getError(5)
            else:
                toSend = mapDirToDate(declination, ascension)
        else:
            #ERROR
            toSend = getError(5)
    return toSend

def attendTME(parameters):
    toSend = b''
    if not parameters:
        toSend = getError(4)
    elif len(parameters) != 14:
        toSend = getError(5)
    else:
        toSend = mapDateToDir(parameters)
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
                qty = abs(deltaDate.days)
                imgParams.imgStart,imgParams.imgEnd = (date1,date2) if deltaDate.total_seconds() < 0 else (date2,date1)
                imgParams.imgQty = qty
                if qty != 0:
                    imgParams.awaitingQTY = True
                else:
                    imgParams.posibleZero = True
                toSend = f'OK{imgParams.imgQty}\r\n'.encode(CODIFICATION)
            else:
                img = apiRequest(date1, True, False)
                if len(img) <=6:
                    toSend = img
                else:
                    toSend = "OK".encode(CODIFICATION) + str(len(img)).encode(CODIFICATION) + ENCODED_HASH + img
        except ValueError:
            toSend = getError(5)
    else:
        if parameters:
            toSend = getError(5)
        else:
            toSend = getError(4)
    return toSend

def attendQTY(parameters):
    if imgParams.posibleZero:
        try:
            qty = int(parameters)
            if qty == 0:
                toSend = "OK\r\n".encode(CODIFICATION)
                imgParams.posibleZero = False
            else:
                toSend = getError(10)
        except ValueError:
            toSend = getError(5)
    elif not imgParams.awaitingQTY:
        toSend = getError(1)  #not previous query for IMG
    elif not parameters:
        toSend = getError(4)  #no parameters
    elif not re.match('^\d+$', parameters):
        toSend = getError(5)  #format error
    elif (int(parameters) < 0 or int(parameters) > imgParams.imgQty): 
        toSend = getError(10)
    else:
        toSend = "OK".encode(CODIFICATION)
        justOneImg = True if (int(parameters) == 1) else False
        for i in range(int(parameters)):
            toSend += getImage(justOneImg)
        if justOneImg:
            toSend += "\r\n".encode(CODIFICATION)
        imgParams.awaitingQTY = False
    return toSend


def getError(errorNum):
    return f"ER{errorNum}\r\n".encode(CODIFICATION) 

def apiRequest(photoDate, justOneImg, checkPhotoAvailability):
    toSend = b''
    deltaSeconds = (photoDate - MIN_DATE).total_seconds()
    if deltaSeconds >= 0:
        if checkPhotoAvailability:
            response = requests.get(f"{API_URL}&date={photoDate.strftime('%Y-%m-%d')}")
        else:
            response = requests.get(f"{API_URL}&date={imgParams.imgStart.strftime('%Y-%m-%d')}")
        if(response.status_code == 200):
            try:
                info = json.loads(response.text)
                if checkPhotoAvailability:
                    toSend += "OK".encode(CODIFICATION)
                elif info["media_type"] == "image":
                    response = requests.get(info["url"])
                    for chunk in response.iter_content():
                        toSend += chunk
                elif (info["media_type"] == "video"):
                    toSend += PREDETERMINED_IMAGE
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
        requestedDate = MIN_DATE + timedelta(days=requestedDays)
        if apiRequest(requestedDate, True, True).decode(CODIFICATION).startswith('ER'):
            toSend = getError(6)
        else:
            toSend = datetime.strftime(requestedDate, f"OK%Y%m%d{ascension}\r\n").encode(CODIFICATION)
    except ValueError:
        toSend = getError(5)
    return toSend

def mapDateToDir(date):
    try:
        #[:-6] obtención de la fecha obvian horas minutos y segundos
        requestedDate = datetime.strptime(date[:-6], "%Y%m%d")
        deltaSeconds = (requestedDate - MIN_DATE).total_seconds()
        if deltaSeconds < 0 or requestedDate > datetime.now() or apiRequest(requestedDate, True, True).decode(CODIFICATION).startswith('ER'):
            toSend = getError(7)
        else:
            ascension = date[8:]
            requestedDays = (requestedDate - MIN_DATE).days
            maxDays = (datetime.now() - MIN_DATE).days
            degrees = requestedDays / maxDays * 180 - 90
            declination = ('+' if degrees >= 0 else '') + str(round(degrees,2)).replace('.','')
            if len(declination) < 5:
                declination += '0'
            toSend = f"OK{(declination[:5] + ascension)}\r\n".encode(CODIFICATION)
    except ValueError:
        toSend = getError(5)
    return toSend

if __name__ == "__main__":
   main()

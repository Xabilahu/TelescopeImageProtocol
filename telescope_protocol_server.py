#!/usr/bin/env python3
import socket, os, signal, re, requests, json, sys
from datetime import datetime, date, timedelta

#Constantes de inicializacion

API_URL = "https://api.nasa.gov/planetary/apod?api_key=TgLGqLIjepX9U4s5HQHots13dt2TCoDGElpE1Gzd" #Token para acceso a API
CODIFICATION = 'us-ascii'
ENCODED_HASH = '#'.encode(CODIFICATION)
MIN_DATE = datetime.strptime("19950615000000", "%Y%m%d%H%M%S")
PORT = 6002 #Puerto por defecto
DEBUG_MODE = False
PREDETERMINED_IMAGE = b''


class ImgParams:
    def __init__(self):
        self.imgEnd = None #Fecha final
        self.imgStart = None #Fecha inicial
        self.awaitingQTY = False #A la espera de un comando QTY
        self.imgQty = None #Cantidad
        self.posibleZero = False #QTY == 0 -> OKps nada

#Variable global con la informacion necesaria para cada sesion (Procesos hijo)
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

    #Inicializacion del socket de escucha
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
    '''
        Metodo encargado de asignar el puerto pasado como parametro
        Entrada : Cadena de caracteres con lo que se ha pasado como parametro al ejecutar el servidor
        Salida : Void
        Excepciones :
            -ValueError: Si el valor introducido no es un numero, o no se corresponde con un numero
            de puerto valido, se devuelve avisa que esta mal y se termina la aplicacion
    '''
    try:
        global PORT 
        tmp = int(port)
        if(tmp >= 0 and tmp <= 65535):
            PORT = tmp
        else:
            raise ValueError
    except ValueError:
        print('\nERROR: Número de puerto incorrecto.\n')
        print('Modo de uso: python3 telescope_protocol_server.py [--debug / -d] [PORT]\n')
        print('En caso de no indicar el número de puerto se asignará el puerto 6002 por defecto.')
        exit(1)

def attendClient(sDialog):
    '''
        Metodo encargado de gestionar la comunicacion servidor-cliente
        Entrada: Socket de dialogo
        Salida: Void
    '''
    crlf = "\r\n".encode(CODIFICATION)
    msg = "".encode(CODIFICATION)
    while True:
        buf = sDialog.recv(1024)
        if not buf:
            break
        msg += buf
        while crlf in msg: #Mientras queden cadenas de finalizacion (CRLF) en el buffer
            '''
            Se realiza esto por si se da el caso de que llegara entrecortado el mensaje 
            o si llegara mas de un comando por mensaje
            '''
            msgSplit = msg.split(crlf)
            try:
                decodedMsg = msgSplit[0].decode(CODIFICATION)
                if DEBUG_MODE:
                    print(f'Mensaje recibido de {sDialog.getsockname()[0]}: {decodedMsg}')
                attendRequest(sDialog, decodedMsg)
            except UnicodeDecodeError:
                #Parametro con formato incorrecto
                sDialog.sendall(getError(5))
            msg = crlf.join(msgSplit[1:]) if len(msgSplit) > 1 else "".encode(CODIFICATION)
    if DEBUG_MODE:
        print(f'Conexion cerrada con {sDialog.getsockname()[0]}')
    sDialog.close()

def attendRequest(sDialog, request):
    ''' 
    Metodo para atender la peticion 
    Entrada: socket dialogo y el comando escrito por el cliente
    Salida: Void
    '''
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
    ''' 
    Metodo para atender la solicitud DIR(solicitud de fecha y hora de la ultima imagen en una determinada direccion)
    Entrada: parametro direccion en el formato indicado en el protocolo
    Salida: String con la fecha y hora
    '''
    #
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
            #ERROR 5 - parametro con formato incorrecto
            toSend = getError(5)
    return toSend

def attendTME(parameters):
    '''
    Metodo para atender la solicitud TME(Solicitud de la direccion de la imagen en determinada fecha y hora)
    Entrada: fecha y hora de la imagen a obtener
    Salida: Direccion de la imagen
    '''
    toSend = b''
    if not parameters:
        toSend = getError(4)
    elif len(parameters) != 14:
        toSend = getError(5)
    else:
        toSend = mapDateToDir(parameters)
    return toSend


def attendIMG(parameters):
    '''
    Metodo para atender la solicitud IMG(Solicitud de imagenes)
    Entrada: fechas y horas de las imagenes a obtener
    Salida: String con un OK, el tamano de la imagen en bytes, un hash y la imagen, o el error oportuno
    '''
    value = re.match('^(\d{14})$|^(\d{28})$', parameters)
    if value:
        value = value.group(0)
        try:
            date1 = datetime.strptime(value[:14], '%Y%m%d%H%M%S')
            qty = 1
            imgParams.imgStart = date1
            toSend = b''
            if (len(value) == 28): #Dos fechas
                date2 = datetime.strptime(value[14:], '%Y%m%d%H%M%S')
                deltaDate = date1 - date2 #Diferencia entre las dos fechas
                qty = abs(deltaDate.days)
                imgParams.imgStart,imgParams.imgEnd = (date1,date2) if deltaDate.total_seconds() < 0 else (date2,date1) #Ordenar fechas
                imgParams.imgQty = qty
                if qty != 0:
                    imgParams.awaitingQTY = True
                else:
                    imgParams.posibleZero = True
                toSend = f'OK{imgParams.imgQty}\r\n'.encode(CODIFICATION)
            else: #Una fecha
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
    '''
    Metodo que atiende las peticiones del tipo QTY
    Entrada: parametros recibidos con la peticion QTY
    Salida: OK + cantidad, o el error oportuno si ha ocurrido alguno
    '''
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
        toSend = getError(1)  #Solicitud de imagen sin haber realizado QTY
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
    '''
    Metodo que construye el mensaje de error que debe devolver el servidor
    Entrada: Numero del error
    Salida: Mensaje de error para cliente
    '''
    return f"ER{errorNum}\r\n".encode(CODIFICATION) 

def apiRequest(photoDate, justOneImg, checkPhotoAvailability):
    '''
    Metodo que se ocupa de realizar las peticiones pertinentes a la API para la obtencion
    de fechas e imagenes.
    Entrada: Fecha de la imagen deseada, booleano indicando si solo se desea una imagen, booleano 
             indicando la disponibilidad de la foto
    Salida: String a enviar al cliente con la informacion deseada (OK+imagen en caso de ser correcto, Err
            + codigo de error asociado)
    '''
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
    '''
    Metodo que obtiene la fecha a partir de la direccion
    Entrada: String con la direccion de la imagen
    Salida: String con la fecha de la imagen
    '''
    try:
        #Convertimos a fecha la declinacion y ascension pasadas por parametro
        requestedHours = datetime.strptime(ascension,'%H%M%S')
        dayPool = (datetime.now() - MIN_DATE).days
        requestedDays = ((float(declination[:3] + '.' + declination[3:])) + 90) / 180 * dayPool 
        requestedDate = MIN_DATE + timedelta(days=requestedDays)
        if apiRequest(requestedDate, True, True).decode(CODIFICATION).startswith('ER'): #Si la api no devuelve ninguna imagen
            toSend = getError(6)
        else:
            toSend = datetime.strftime(requestedDate, f"OK%Y%m%d{ascension}\r\n").encode(CODIFICATION)
    except ValueError:
        toSend = getError(5)
    return toSend

def mapDateToDir(date):
    '''
    Metodo que obtiene la direccion de una imagen a partir de una fecha
    Entrada: String con la fecha
    Salida: Direccion de la imagen
    '''
    try:
        #[:-6] obtención de la fecha obviando horas minutos y segundos
        requestedDate = datetime.strptime(date[:-6], "%Y%m%d")
        deltaSeconds = (requestedDate - MIN_DATE).total_seconds()
        if deltaSeconds < 0 or requestedDate > datetime.now() or apiRequest(requestedDate, True, True).decode(CODIFICATION).startswith('ER'):
            toSend = getError(7)
        else:
            #Convertimos fecha a declinacion y ascension
            ascension = date[8:]
            requestedDays = (requestedDate - MIN_DATE).days
            maxDays = (datetime.now() - MIN_DATE).days
            degrees = requestedDays / maxDays * 180 - 90 #Calculo de los grados de la declinacion
            declination = ('+' if degrees >= 0 else '') + str(round(degrees,2)).replace('.','')
            if len(declination) < 5:
                declination += '0'
            toSend = f"OK{(declination[:5] + ascension)}\r\n".encode(CODIFICATION)
    except ValueError:
        toSend = getError(5)
    return toSend

if __name__ == "__main__":
   main()

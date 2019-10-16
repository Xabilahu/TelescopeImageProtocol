#!/usr/bin/env python3

import socket, sys, os
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

PORT = 6002
CODIFICATION = 'us-ascii'
CRLF = '\r\n'.encode(CODIFICATION)

class Menu:
	Dir, Tme, Img, Exit = range(1,5)
	Options = ( "Solicitud de fecha y hora", "Solicitud de dirección", "Solicitud de imágenes", "Salir" )

	def menu():
		print( "+{}+".format( '-' * 50 ) )
		for i,option in enumerate( Menu.Options, 1 ):
			print( "| {}.- {:<45}|".format( i, option ) )
		print( "+{}+".format( '-' * 50 ) )

		while True:
			try:
				selected = int( input( "Selecciona una opción: " ) )
			except:
				print( "Opción no válida." )
				continue
			if 0 < selected <= len( Menu.Options ):
				return selected
			else:
				print( "Opción no válida." )

def main():
    if (len(sys.argv) != 2):
        print('Modo de uso: python3 telescope_protocol_client.py <SERVER-IP-ADRESS>')
        exit(1)
    else:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((sys.argv[1], PORT))
        option = -1
        while option != Menu.Exit:
            option = Menu.menu()
            if option == Menu.Dir:
                print('Introduzca la declinación: ')
                toSend = f'DIR{input()}'
                print('Introduzca la ascensión: ')
                toSend += input()
            elif option == Menu.Tme:
                print('Introduzca la fecha y hora: ')
                toSend = f'TME{input()}'
            elif option == Menu.Img:
                toSend = 'IMG'
                while True:
                    print('¿Quiere solicitar imagenes en un rango de fechas?[s-n]: ')
                    option = input()
                    if option == 'S' or option == 's':
                        date1 = input('Introduzca la primera fecha y hora: ')
                        date2 = input('Introduzca la segunda fecha y hora: ')
                        toSend += date1 + date2
                        break
                    elif option == 'N' or option == 'n':
                        date = input('Introduzca la fecha y hora: ')
                        toSend += date
                        break
                toSend = toSend.encode(CODIFICATION) + CRLF
                s.sendall(toSend)
                msg = recibirMensaje(s)
                if msg.startswith('ER'.encode(CODIFICATION)):
                    print(decodeError(int(msg[2:-2])))
                    continue
                images = 'imágenes'
                image = 'imagen'
                print(f'El servidor dispone de {msg[2:-2].decode(CODIFICATION)} {images if int(msg[2:-2].decode(CODIFICATION)) != 1 else image}.')
                qty = input('Introduzca la cantidad de imágenes que quiere enviar: ')
                toSend = f'QTY{qty}\r\n'.encode(CODIFICATION)
                s.sendall(toSend)
                msg = b''
                cont = False
                images = []
                qty = int(qty)
                buf = s.recv( 1024 )
                msg += buf
                if msg.startswith('ER'.encode(CODIFICATION)):
                    print(decodeError(int(msg.decode(CODIFICATION)[2:-2])))
                else:
                    while len(images) != qty:
                        buf = s.recv( 1024 )
                        msg += buf
                        partition = msg.split('#'.encode(CODIFICATION))
                        size = int(partition[0][2:])
                        if len(msg) >= size + len(partition[0]):
                            msg, images = extractImages(msg, images)
                    for i, im in enumerate(images):
                        fImg = open(f'tmpIMG{i}.jpg', 'wb')
                        fImg.write(im)
                        fImg.close()
                        img = mpimg.imread(f'tmpIMG{i}.jpg')
                        imgplot = plt.imshow(img)
                        plt.axis('off')
                        plt.show()
                        os.remove(f'tmpIMG{i}.jpg')

        s.close()
        exit(0)

def decodeError(codeError):
    toSend = ''
    if codeError == 1:
        pass
    elif codeError == 2:
        pass
    elif codeError == 3:
        pass
    elif codeError == 4:
        pass
    elif codeError == 5:
        pass
    elif codeError == 6:
        pass
    elif codeError == 7:
        pass
    elif codeError == 8:
        pass
    elif codeError == 9:
        pass
    elif codeError == 10:
        pass
    else:
        pass

def recibirMensaje(sock):
    msg = b''
    while True:
        buf = sock.recv( 1024 )
        msg += buf
        if CRLF in msg:
            break
    return msg

def extractImages(msg, images):
    msgText = msg
    if len(msgText) != 2 and '#'.encode(CODIFICATION) in msgText:
        index = msgText.index('#'.encode(CODIFICATION))
        size = int(msg[2:index].decode(CODIFICATION))
        image = msg[1 + index:size + 1 + index]
        if len(image) == size:
            images.append(image)
            msg = msg[:2] + msg[size + 1 + index:]
            return extractImages(msg, images)
    return msg, images


if __name__ == "__main__":
    main()
    
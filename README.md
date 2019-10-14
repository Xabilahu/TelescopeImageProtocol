Aplicación para el acceso a las imágenes de un telescopio
=========================================================

Descripción:
------------

Esta aplicación permite el acceso a las imágenes obtenidas por un telescopio. La aplicación permitirá conocer la fecha y hora de la última imagen obtenida en determinada dirección, conocer la dirección de la imagen obtenida en determinada fecha y hora y descargar una o varias imágenes. La aplicación no permite mover el telescopio ni indicar cuándo se ha de tomar una imagen.

La aplicación usará TCP como protocolo de transporte para asegurar la correcta transferencia de las imágenes. Para simplificar la aplicación no tendremos en cuenta la autenticación de los clientes.

Protocolo:
----------

*Sintaxis y semántica:*

Todos los comandos, respuestas y parámetros serán cadenas de caracteres US-ASCII, salvo el contenido de las imágenes. Todos los comandos y respuestas serán de 3 caracteres y los parámetros irán después del comando/respuesta, sin ningún tipo de separación. Para indicar el final de todos los mensajes (salvo cuando se envía una o varias imágenes en respuesta al comando IMG) se utilizarán los caracteres CR+LF, es decir, los bytes 13 y 10.

*Comandos:*

||||
|--- |--- |--- |
|Comando|Parámetros|Descripción/ Semántica|
|DIR|Dirección|Solicitud de fecha y hora de la última imagen en una determinada dirección.|
|TME|Fecha y hora|Solicitud de la dirección de la imagen en determinada fecha y hora.|
|IMG|Fecha y hora [+ Fecha y hora]|Solicitud de imágenes.|
|QTY|Cantidad|Confirmación de la solicitud de imágenes.|

*Respuestas:*

||||
|--- |--- |--- |
|Respuesta|Parámetros|Descripción/ Semántica|
|OK+|[ Fecha y hora \| Dirección \| Cantidad \| Imágenes ]|Respuesta positiva. Todo ha ido correctamente.|
|ER-|Código de error|Respuesta negativa. Ha habido algún problema.|

\* Los corchetes \[\] indican que el parámetro es opcional. La barra vertical | indica un OR lógico.

*Formato de los parámetros:*

-   El parámetro “Fecha y hora” se compondrá de 14 caracteres siguiendo el formato AAAAMMDDHmmss. Es decir 4 dígitos para el año, 2 para el mes, 2 para el día, 2 para la hora (0-23), 2 para los minutos (0-59) y 2 para los segundos (0-59). La hora será siempre en base a UTC.
-   La dirección se compondrá siempre de 11 caracteres que representarán dos valores: primero la declinación y luego la ascensión recta.

    -   La declinación está siempre entre -90º y +90º y se indicará con 5 caracteres: primero el signo ('+' o '-'), luego dos dígitos para la parte entera y finalmente 2 dígitos decimales. Por ejemplo, la declinación 43,71º se indicará con los caracteres '+4371'.
    -   La ascensión recta se indicará mediante 6 dígitos en el formato HHmmss. Es decir, dos dígitos para la hora (0-23), dos para los minutos (0-59) y dos para los segundos (0-59).
-   La cantidad de imágenes (como respuesta al comando IMG o como parámetro del comando QTY) se indica como un número entero positivo de tamaño variable. El valor cero también será válido. En cualquiera de los dos casos el salto de línea de fin del mensaje limitará el tamaño del parámetro.
-   Para enviar imágenes (como respuesta al comando QTY o IMG) el servidor deberá enviar antes de cada imagen un parámetro de tamaño variable indicando el tamaño de la imagen en bytes, finalizando con el carácter '\#'. No habrá ninguna otra separación que estos dos valores (tamaño y carácter '\#') entre las diferentes imágenes. Recuerda que al final de este mensaje no hay que añadir los caracteres CR+LF que indican el final del mensaje.

**Procedimientos:**

*Cuestiones generales*

En el caso de un error el servidor responderá con una respuesta negativa y un código de error. A continuación se listan los códigos considerados genéricos:

|||
|--- |--- |
|Código|Error|
|01|Comando inesperado.|
|02|Comando desconocido.|
|03|Parámetro inesperado. Se ha recibido un parámetro donde no se esperaba.|
|04|Falta parámetro. Falta un parámetro que no es opcional.|
|05|Parámetro con formato incorrecto.|

*Solicitud de fecha y hora de la última imagen en una determinada dirección*

El cliente enviará el comando DIR junto con el parámetro indicando una dirección. El servidor enviará una respuesta positiva con la fecha y hora de la última imagen en esa dirección. En caso de que no haya ninguna imagen en esa dirección el servidor enviará una respuesta negativa y el código de error 06.

*Solicitud de la dirección de la imagen en determinada fecha y hora*

El cliente enviará el comando TME con una fecha y hora. En caso de que no haya ninguna imagen en esa fecha y hora el servidor enviará una respuesta negativa y el código de error 07. En caso contrario el servidor enviará una respuesta positiva junto con la dirección en la que se tomó la imagen en esa fecha y hora.

*Solicitud de descarga de una imagen*

El cliente enviará el comando IMG y una fecha y hora. En caso de que no exista una imagen en esa fecha y hora el servidor responderá enviando una respuesta de error con el código 08. Si la imagen existe, pero el servidor no consigue acceder a ella enviará el código de error 09. Si todo ha ido bien el servidor enviará una respuesta positiva junto con el tamaño de la imagen en bytes y el contenido de la imagen (para más detalle ver el apartado de sintaxis).

*Solicitud de descarga de varias imágenes*

El cliente enviará el comando IMG y dos parámetros de fecha y hora (el orden de los parámetros es indiferente). El servidor responderá con una respuesta positiva informando del número de imágenes obtenidas entre los dos momentos indicados por la fecha y la hora. Si la respuesta es 0 el procedimiento quedará finalizado. En caso contrario, el cliente deberá enviar el comando QTY indicando como parámetro el número de imágenes que desea recibir. Si el parámetro es mayor al número de imágenes disponible el servidor responderá con un mensaje de error con código 10. Si el servidor no puede acceder a alguna de las imágenes responderá con un mensaje de error y el código 11. Si no, responderá positivamente y enviará las imágenes siguiendo el formato indicado en el apartado de sintaxis.

Es correcto enviar el parámetro '0' con el comando QTY. En este caso el servidor debe interpretar que el cliente quiere cancelar el envío de las imágenes y deberá responder afirmativamente y sin parámetros.

# Problemas encontrados durante el desarrollo

## Entorno
- uv add falló por timeout al descargar pyarrow; se resolvió con UV_HTTP_TIMEOUT=300, UV_HTTP_CONNECT_TIMEOUT=60 y UV_HTTP_RETRIES=10.
- git push falló por conexión inestable (RPC failed, curl 55); se resolvió con git config http.postBuffer 524288000.
- Aviso de Git LF/CRLF en Windows: no afecta al código.

## Servidor MCP (BCRP)
- La API escribe setiembre como "Set" en series diarias y "Sep" en mensuales; el comentario del curso solo mencionaba "Set".
- Pedir 2024-T1 a la API no da error, pero devuelve 0 datos; hay que convertirlo a 2024-1.
- La API limita pedidos seguidos: las pruebas tardaron entre 20 y 82 segundos, y en una consulta en vivo falló; el servidor informó el error y Claude reintentó.

## ENAHO
- La pobreza rural por personas (facpob07) da 39.44 %, frente al 39.3 % de referencia (diferencia de 0.14 puntos). La referencia se calcula por hogares (factor07 × mieperho), y con ese método se obtiene 39.30 %. No se ajustó la tolerancia: se documenta la diferencia de método.
- Los departamentos por personas (facpob07) difieren de la tabla de la Sesión 16 en 14 de 25 casos (máximo 0.52 puntos, Puno). Por hogares (factor07 × mieperho) coinciden los 25 a 0.05 puntos o menos: las diferencias se explican por el método, no por errores de limpieza.
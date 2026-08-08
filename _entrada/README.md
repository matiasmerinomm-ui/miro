# Carpeta de entrada del verificador

Poné acá el contenido crudo que querés verificar y estandarizar. Cuando subís o
editás un archivo en esta carpeta, el robot **"Verificar y estandarizar listas"**
lo procesa solo y deja el resultado en la carpeta `_salida/`.

## Cómo nombrar los archivos

- `peliculas.txt` (o `.m3u`) → verifica **todo** y saca los caídos.
- `canales.txt` → igual, verifica todo.
- Cualquier nombre con la palabra **"serie"** (ej. `series.txt`) → **muestreo por
  serie**: prueba 1 episodio por serie; si anda deja la serie entera, si está
  caído la saca.

## Qué obtenés

En `_salida/` aparece:

- `<nombre>.m3u` → la lista **limpia y estandarizada**, lista para copiar y pegar
  en el maestro (`peliculas.m3u`, `series.m3u`, `lista.m3u`).
- `<nombre>_caidos.m3u` → **solo lo que NO anda** (nombre, categoría y URL), para
  ir a buscar reemplazos.
- `<nombre>_reporte.html` → reporte con colores (verde/amarillo/rojo) y buscador.

Además, cuando el robot termina, en la pestaña **Actions** te muestra un resumen
en el navegador con la lista de lo que se cayó (sin bajar nada).

# FollowBack Explorer

Aplicación Streamlit para analizar exportaciones de seguidores y seguidos de
Instagram. El usuario importa dos HTML desde su computadora; los archivos se
procesan en memoria y no se escriben en almacenamiento permanente.

## Uso local

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

La aplicación presenta dos importadores independientes: uno para el HTML de
seguidores y otro para el de seguidos. Se aceptan extensiones `.html` y `.htm`,
y los nombres de archivo pueden ser cualesquiera. El contenido debe ser una
exportación de Instagram del tipo correspondiente. Tras seleccionar ambos
archivos, pulsa **Analizar mis relaciones**.

Si sustituyes un archivo, la aplicación detecta que los resultados visibles
pertenecen a una selección anterior y pide volver a ejecutar el análisis.
Mientras no se analiza, ambos archivos, su contenido y la selección se
mantienen únicamente en la sesión de Streamlit. Las tablas, búsquedas, filtros,
gráficas y métricas existentes se conservan.

## Privacidad

No se inicia sesión en Instagram ni se solicitan credenciales. Los archivos
subidos se procesan en memoria y la aplicación no los escribe en disco ni los
envía a APIs externas. En una ejecución local, el procesamiento ocurre en el
equipo del usuario. En Streamlit Community Cloud, el navegador envía los
archivos a la instancia de la aplicación para procesarlos durante la sesión;
no se debe considerar eso como procesamiento local. Los DataFrames de
resultados permanecen en la memoria de la sesión hasta que esta termina.

## Dependencias

`requirements.txt` contiene solo las dependencias necesarias para ejecutar la
aplicación: Streamlit, Pandas y Plotly. No se requieren los HTML ni el Excel en
el repositorio o en el servidor antes de abrir la aplicación.

Para desarrollar, ejecutar las pruebas o regenerar el informe histórico de
comparación con Excel:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python validate_exports.py
```

`openpyxl` y `pytest` están solo en `requirements-dev.txt`: el libro de
referencia y el validador histórico no son dependencias de ejecución de la app.
El informe de validación no contiene identificadores de cuenta.

## Streamlit Community Cloud

El punto de entrada es `app.py`. Para desplegar, selecciona este archivo como
main file; Community Cloud instalará las dependencias de `requirements.txt`.
La configuración `.streamlit/config.toml` define el tema oscuro y desactiva
estadísticas de uso, sin fijar una dirección/puerto local. El despliegue no se
realiza automáticamente desde este proyecto.

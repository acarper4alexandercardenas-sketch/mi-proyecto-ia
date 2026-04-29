FROM python:3.13
WORKDIR /app
COPY equipo.csv .
COPY lector_csv.py .
RUN pip install openpyxl
CMD ["python", "lector_csv.py"]
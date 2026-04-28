import csv

def leer_equipo(archivo):
    equipo = []
    with open(archivo, encoding='utf-8') as f:
        lector = csv.DictReader(f)
        for fila in lector:
            equipo.append(fila)
            
    return equipo

def mostrar_resumen(equipo):
    total_personas = 0
    con_coordinador = 0
    sin_coordinador = 0

    print("=" * 45)
    print("RESUMEN DEL EQUIPO DE TI")
    print("=" * 45)

    for area in equipo:
        personas = int(area['personas'])
        total_personas += personas
        if area['coordinador'] == 'Si':
            con_coordinador += 1
        else:
            sin_coordinador += 1
        print(f"{area['area']:20} | {personas} personas | {area['sistema']}")

    print("=" * 45)
    print(f"Total personas     : {total_personas}")
    print(f"Areas con coord.   : {con_coordinador}")
    print(f"Areas sin coord.   : {sin_coordinador}")
    print("=" * 45)

def filtrar_por_sistema(equipo, sistema):
    print(f"\nAreas que usan {sistema}:")
    print("-" * 35)
    for area in equipo:
        if sistema.upper() in area['sistema'].upper():
            print(f"- {area['area']} ({area['personas']} personas)")


equipo = leer_equipo('equipo.csv')
mostrar_resumen(equipo)

sistema_buscar = input("\n¿Qué sistema quieres buscar? ")
filtrar_por_sistema(equipo, sistema_buscar)




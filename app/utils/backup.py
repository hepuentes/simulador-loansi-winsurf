"""
BACKUP.PY - Utilidades para backup y recuperación
==================================================
"""

import os
import shutil
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent.resolve()
BACKUP_DIR = BASE_DIR / 'backups'


def crear_backup_con_rotacion(archivo_origen, prefijo="backup", max_backups=7):
    """
    Crea un backup de un archivo con rotación automática.
    Mantiene solo los últimos N backups.

    Args:
        archivo_origen: Path del archivo a respaldar
        prefijo: Prefijo para el nombre del backup
        max_backups: Número máximo de backups a mantener

    Returns:
        str: Path del backup creado o None si falla
    """
    try:
        # Verificar que el archivo origen existe
        if not os.path.exists(archivo_origen):
            print(f"⚠️ Archivo no existe para backup: {archivo_origen}")
            return None

        # Crear directorio de backups si no existe
        BACKUP_DIR.mkdir(exist_ok=True)

        # Generar nombre del backup con timestamp
        nombre_archivo = os.path.basename(archivo_origen)
        nombre_base, extension = os.path.splitext(nombre_archivo)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_backup = f"{prefijo}_{nombre_base}_{timestamp}{extension}"
        ruta_backup = BACKUP_DIR / nombre_backup

        # Copiar archivo
        shutil.copy2(archivo_origen, ruta_backup)
        print(f"✅ Backup creado: {ruta_backup}")

        # Rotación: eliminar backups antiguos
        patron = f"{prefijo}_{nombre_base}_*{extension}"
        backups = sorted(BACKUP_DIR.glob(patron), key=os.path.getmtime, reverse=True)

        if len(backups) > max_backups:
            for backup_antiguo in backups[max_backups:]:
                try:
                    os.remove(backup_antiguo)
                    print(f"🗑️ Backup antiguo eliminado: {backup_antiguo}")
                except OSError as e:
                    print(f"⚠️ No se pudo eliminar backup antiguo: {e}")

        return str(ruta_backup)

    except Exception as e:
        print(f"❌ Error creando backup: {e}")
        return None


def recuperar_desde_backup_mas_reciente(nombre_archivo_base, destino=None):
    """
    Recupera un archivo desde el backup más reciente.

    Args:
        nombre_archivo_base: Nombre base del archivo (sin timestamp)
        destino: Path de destino (si None, usa el path original)

    Returns:
        bool: True si se recuperó exitosamente
    """
    try:
        # Buscar backups que coincidan
        patron = f"backup_{nombre_archivo_base}_*"
        backups = sorted(BACKUP_DIR.glob(patron), key=os.path.getmtime, reverse=True)

        if not backups:
            print(f"⚠️ No se encontraron backups para: {nombre_archivo_base}")
            return False

        backup_mas_reciente = backups[0]
        print(f"📂 Backup más reciente encontrado: {backup_mas_reciente}")

        # Determinar destino
        if destino is None:
            # Reconstruir nombre original
            nombre_base, extension = os.path.splitext(nombre_archivo_base)
            destino = BASE_DIR / f"{nombre_base}{extension}"

        # Copiar backup al destino
        shutil.copy2(backup_mas_reciente, destino)
        print(f"✅ Archivo recuperado: {destino}")

        return True

    except Exception as e:
        print(f"❌ Error recuperando desde backup: {e}")
        return False


def listar_backups(nombre_archivo_base=None):
    """
    Lista todos los backups disponibles.

    Args:
        nombre_archivo_base: Filtrar por nombre de archivo (opcional)

    Returns:
        list: Lista de diccionarios con info de backups
    """
    try:
        if not BACKUP_DIR.exists():
            return []

        if nombre_archivo_base:
            patron = f"backup_{nombre_archivo_base}_*"
        else:
            patron = "backup_*"

        backups = []
        for backup_path in sorted(BACKUP_DIR.glob(patron), key=os.path.getmtime, reverse=True):
            stat = backup_path.stat()
            backups.append({
                'nombre': backup_path.name,
                'path': str(backup_path),
                'tamaño': stat.st_size,
                'fecha_modificacion': datetime.fromtimestamp(stat.st_mtime).isoformat()
            })

        return backups

    except Exception as e:
        print(f"❌ Error listando backups: {e}")
        return []

import hashlib
import hmac
import os
import secrets
from datetime import datetime

import mssql_python
from dotenv import load_dotenv

#Exito
def _ok(datos=None):
    return{"ok":True, "datos":datos}

#Error y su respuesta
def _error(codigo,mensaje, detalle=None):
    return{"ok":False,"error":codigo, "mensaje":mensaje, "detalle":detalle}

#Maneja los errores de SQL
def _error_excepcion(excepcion):
    texto = str(excepcion).upper()
    if "UNIQUE" in texto or "2627" in texto:
        return _error("usuario_existe", "Ese nombre de usuario ya existe", str(excepcion))
    if "FOREIGN KEY" in texto:
        return _error("imagen_invalida", "La imagen elegida no existe", str(excepcion))
    return _error("error_bd", "Error en la base de datos", str(excepcion))

def _obtener_fecha_sql() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

load_dotenv()

LONGITUD_MAX_USUARIO = 100

class BaseDatos:

    def __init__(self,servidor=None,base=None,usuario=None,password=None):
        
        self.servidor = servidor or os.environ.get("DB_SERVER","localhost")
        self.base = base or os.environ.get("DB_NAME", "maniacos")
        self.usuario = usuario or os.environ.get("DB_USER","maniacos")
        self.password = password or os.environ.get("DB_PWD")
        self._conn = None
        
    
    """Metodo para conectarnos a la Base de datos de SQL Server usando la biblioteca mssql_python"""    
    def conectar(self):
        if self._conn is None:
            self._conn = mssql_python.connect(
                server=self.servidor,
                database=self.base,
                uid=self.usuario,
                pwd=self.password,
                encrypt="yes",
                trust_server_certificate="yes",
            )
        return self
    
    def cerrar_conexion(self):
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None
    
#Cuando se inicsia comienza la conexion
    def __enter__(self):
        return self.conectar()
    
#Cuando se cierra se desconecta
    def _exit__(self,exc_type, exc_val, exc_tb):
        self.cerrar_conexion()
        return False
    
    """Metodo para ejecutar cualquier query en la base de datos, tenemos una variable, 
    la cual nos duvuelve una fila, una abala completa o solo informacion de que se afecto"""
    def _ejecutar_query(self,sql,parametros=(),devolver=None):
        """Primero checamos la conexion a la base de datos, si no pues nos conectamos"""
        if self._conn is None:
            self.conectar()
            
        cursor = self._conn.cursor()
        
        try:
            """if: Aqui es para cuando hagamos consultas o peticiones que lleven parametros, como inserciones o registros de usuarios"""
            """else: En este es cuando nuestras consultas o peticiones no lleven parametros, cuando carguemos un chat o saber quien se conecto"""
            if parametros:
                cursor.execute(sql,parametros)
            
            else:
                cursor.execute(sql)
            
            if devolver == "una":
                columnas = [c[0] for c in cursor.description]
                fila = cursor.fetchone()
                resultado = dict(zip(columnas,fila)) if fila else None
            elif devolver == "toda":
                columnas = [c[0] for c in cursor.description]
                resultado = [dict(zip(columnas,f)) for f in cursor.fetchall()]
            else:
                resultado = cursor.rowcount
            
            """Funcion que se ejecuta para asegurar que los cambios son permamentes en la base de datos"""
            self._conn.commit()
            return resultado
        
        except Exception:
            """Esta funcion es por si algo falla y ya no se ejecuta todo el query"""
            self._conn.rollback()
            raise
        
        finally:
            """Cierra la conexion"""
            cursor.close()
            

    #Registrar un usuario
    def registrar_usuario(self,usuario,passwrd,imagen_id = 1):
        usuario = (usuario or "").strip()
        
        if not usuario or (len(usuario) > LONGITUD_MAX_USUARIO):
            return _error("datos_invalidos",f"El nombre del usuario debe tener entre 1 y {LONGITUD_MAX_USUARIO} caracteres")
        if not passwrd:
            raise _error("datos_invalidos","No se puede tener una contraseña vacia")
        
        try:
            query = "INSERT INTO maniacosdb.usuarios (usuario, contrasena, imagen_local_id, fecha_registro) VALUES (?, ?, ?, ?)"
            fecha = _obtener_fecha_sql()
            insercion = self._ejecutar_query(query,(usuario,passwrd,imagen_id,fecha))
            if not insercion:
                return _error("error_insercion", "No se logro la insercion del usuario")
            return _ok(insercion)
        except Exception as e:
            return _error_excepcion(e)
    
    #Checar login
    def validar_login(self,usuario,passwd):
        try:
            query = "SELECT id, usuario, contrasena, imagen_local_id FROM maniacosdb.usuarios WHERE usuario = ?"
            resultado = self._ejecutar_query(query,usuario,devolver="una")
        except Exception as e:
            return _error_excepcion(e)
        
        if resultado is None or (resultado["contrasena"] != passwd):
            return _error("credenciales_no_validas",f"Contraseña y/o usuario incorrectos")
        del resultado["contrasena"]
        
        return _ok(resultado)
            
        
    
# mixins.py
from pymongo import MongoClient
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

class AutoCleanMongoMixin:
    """Mezcla que elimina campos nulos o vacíos de documentos Mongo después de save()."""

    MONGO_URI = "mongodb+srv://jesusmedina0921:rtYRvTorUpIDCqDz@cluster0.xvyzd3u.mongodb.net/Barberia?retryWrites=true&w=majority&appName=Cluster0"
    DB_NAME = "Barberia"
    COLLECTION_NAME = "api_user"

    CLEAN_FIELDS = []

    def mongo_clean(self):
        unset_fields = {}

        for field in self.CLEAN_FIELDS:
            value = getattr(self, field, None)
            if value is None or value == "" or (isinstance(value, list) and not value):
                unset_fields[field] = "" 

        if unset_fields:
            client = None
            try:
                client = MongoClient(self.MONGO_URI)
                db = client[self.DB_NAME]
                collection = db[self.COLLECTION_NAME]

                # self.pk ya es el ObjectId que mapea a _id de MongoDB
                # Asegúrate de que self.pk sea un ObjectId válido para la consulta
                mongo_document_id = self.pk 
                
                # if not isinstance(mongo_document_id, ObjectId):
                #     # Si por alguna razón no es un ObjectId directo (Django lo maneja, pero por si acaso)
                #     try:
                #         mongo_document_id = ObjectId(str(self.pk))
                #     except Exception as e:
                #         logger.error(f"Error al convertir self.pk '{self.pk}' a ObjectId: {e}")
                #         return

                logger.info(f"Buscando documento en MongoDB con _id: {mongo_document_id}")

                # ¡CAMBIO CLAVE AQUÍ! Busca por '_id', no por 'id'
                mongo_document = collection.find_one({"_id": mongo_document_id}) 

                if mongo_document:
                    # Si el documento ya se encontró por su _id, no necesitas obtenerlo de nuevo
                    # El mongo_document_id ya es el _id que necesitas para la actualización
                    
                    logger.info(f"Documento encontrado. El _id de MongoDB es: {mongo_document_id}")
                    logger.info(f"Campos a eliminar ($unset): {unset_fields}")
                    logger.info(f"Colección: {self.COLLECTION_NAME}, Base de Datos: {self.DB_NAME}")

                    result = collection.update_one(
                        {"_id": mongo_document_id}, # Usa el _id real de MongoDB para la actualización
                        {"$unset": unset_fields}
                    )
                    logger.info(f"Resultado de la limpieza en MongoDB: Coincidencias {result.matched_count}, Modificados {result.modified_count}")
                    if result.matched_count == 0:
                        logger.warning(f"Advertencia: No se encontró ningún documento para _id: {mongo_document_id} en la colección {self.COLLECTION_NAME} durante la actualización.")
                    if result.modified_count > 0:
                        logger.info(f"Documento con _id: {mongo_document_id} modificado exitosamente.")
                else:
                    logger.warning(f"Advertencia: No se encontró ningún documento en MongoDB con _id: {mongo_document_id}. Esto podría indicar un problema de sincronización o que el documento no se guardó correctamente.")

            except Exception as e:
                logger.error(f"Error durante la operación de limpieza de MongoDB: {e}")
            finally:
                if client:
                    client.close()
        else:
            logger.info("No hay campos para eliminar.")
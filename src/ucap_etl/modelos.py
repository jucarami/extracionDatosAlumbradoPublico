"""Modelo de datos del ETL.

Un RegistroUCAP es una fila del CSV: el grano es UCAP-dentro-de-documento,
igual que el Consolidado General.
"""

from __future__ import annotations

from dataclasses import dataclass
from .texto import normalizar_descripcion


@dataclass(frozen=True)
class ContextoPagina:
    """Encabezado de una hoja del formato: proyecto y documento asociado."""

    proyecto: str = ""
    tipo: str = ""       # "SS" o "SN"
    numero: str = ""     # p. ej. "193679"

    @property
    def esta_completo(self) -> bool:
        return bool(self.tipo and self.numero)

    @property
    def documento(self) -> str:
        """El número de la solicitud, sin el prefijo SS/SN.

        El número es único en todo el universo de documentos: no existe un SS
        y un SN con el mismo número. El tipo se conserva en su propia columna
        para trazabilidad, pero no hace parte de la clave.
        """
        return self.numero if self.esta_completo else ""
 
    
@dataclass(frozen=True)
class RegistroUCAP:
    """Una línea de detalle del formato UCAP."""

    pagina: int
    contexto: ContextoPagina
    codigo: str
    descripcion: str
    colocar: int | float | None
    quitar: int | float | None
    fuente: str
    @property
    
    def descripcion_normalizada(self) -> str:
        return normalizar_descripcion(self.descripcion)
     
     
    @property   
    def movimiento(self) -> str:
        """COLOCAR, QUITAR, AMBOS o NULO. Deriva el sentido de la línea."""
        pone = self.colocar not in (None, 0)
        saca = self.quitar not in (None, 0)
        if pone and saca:
            return "AMBOS"
        if pone:
            return "COLOCAR"
        if saca:
            return "QUITAR"
        return "NULO"
    
    def clave_consolidacion(self) -> str:
        """Llave hacia el catálogo de UCAPs.

        Es el código crudo tal como viene en el documento. Los ítems sin
        código llevan el marcador 'SIN CODIGO' seguido de la descripción
        normalizada, que es lo que los distingue entre sí: crucetas y puntas
        captadoras son físicamente distintas y no pueden colapsar.

        No es única por fila: un mismo UCAP aparece en muchos documentos.
        """
        if self.codigo:
            return self.codigo
        return f"SIN CODIGO|{self.descripcion_normalizada}"


    def a_dict(self) -> dict[str, object]:
        """Proyecta el registro al esquema del CSV."""
        return {
            "Pagina": self.pagina,
            "Tipo": self.contexto.tipo,
            "SS/SN": self.contexto.numero,
            "Proyecto": self.contexto.proyecto,
            "codigo UCAP": self.codigo,
            "Descripcion UCAP": self.descripcion,
            "Colocar": self.colocar,
            "Quitar": self.quitar,
            "Descripcion Normalizada": self.descripcion_normalizada,
            "Fuente": self.fuente,
            "Clave Consolidacion": self.clave_consolidacion(),
        }
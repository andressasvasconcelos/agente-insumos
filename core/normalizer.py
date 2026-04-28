"""
Normalização de descrições de insumos de construção civil.

Trata:
- Case (lowercase para comparação)
- Acentos (remoção)
- Abreviações comuns do setor (CP-II → Cimento Portland)
- Espaços e pontuação redundante
"""

import re
import unicodedata


# Dicionário de abreviações da construção civil
# Adicione/edite conforme o vocabulário da sua empresa
ABREVIACOES = {
    r"\bcp[-\s]?ii\b": "cimento portland ii",
    r"\bcp[-\s]?iii\b": "cimento portland iii",
    r"\bcp[-\s]?iv\b": "cimento portland iv",
    r"\bcp[-\s]?v\b": "cimento portland v",
    r"\barg\b": "argamassa",
    r"\bconc\b": "concreto",
    r"\brev\b": "revestimento",
    r"\bcol\b": "colante",
    r"\bhidr\b": "hidraulico",
    r"\beletr\b": "eletrico",
    r"\bpvc\b": "policloreto de vinila pvc",
    r"\bppr\b": "polipropileno ppr",
    r"\bcpvc\b": "cpvc clorado",
    r"\binox\b": "aco inox",
    r"\bmdf\b": "mdf madeira",
    r"\bosb\b": "osb madeira",
    r"\bgesso acart\b": "gesso acartonado drywall",
    r"\bdrywall\b": "drywall gesso acartonado",
}

# Caracteres de pontuação a normalizar para espaço
PONTUACAO_PARA_ESPACO = r'[/\\\-_,;:|()\[\]{}"]'


def remover_acentos(texto: str) -> str:
    """Remove acentos mantendo o caractere base."""
    if not isinstance(texto, str):
        return ""
    nfd = unicodedata.normalize("NFD", texto)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def expandir_abreviacoes(texto: str) -> str:
    """Expande abreviações comuns do setor de construção civil."""
    resultado = texto
    for padrao, expansao in ABREVIACOES.items():
        resultado = re.sub(padrao, expansao, resultado, flags=re.IGNORECASE)
    return resultado


def normalizar(texto: str) -> str:
    """
    Pipeline completo de normalização para comparação.
    
    Mantém apenas alfanuméricos + espaços, em lowercase, sem acentos.
    NÃO usar para exibição — só para matching interno.
    """
    if not isinstance(texto, str) or not texto.strip():
        return ""
    
    t = texto.lower()
    t = remover_acentos(t)
    t = expandir_abreviacoes(t)
    t = re.sub(PONTUACAO_PARA_ESPACO, " ", t)
    # Mantém só alfanumérico, espaço e ponto/vírgula em medidas (ex: 1.5mm)
    t = re.sub(r"[^a-z0-9\s.]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


if __name__ == "__main__":
    # Testes manuais
    casos = [
        "Cimento CP-II 50kg",
        "Argamassa Quartzolit 20kg - Branca",
        "Tubo PVC Soldável Ø50mm",
        "Tinta Acrílica Suvinil 18L",
    ]
    for c in casos:
        print(f"{c!r:50} → {normalizar(c)!r}")

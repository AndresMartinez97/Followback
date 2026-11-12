"""Compare the current Instagram HTML exports with the reference Excel workbook."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from modules.analysis import compare_data_sources
from modules.data_cleaner import clean_records
from modules.excel_reader import read_follow_data
from modules.parser import read_html_data


PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR.parent
REPORT_PATH = PROJECT_DIR / "reports" / "html_excel_validation.md"


def _format_names(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "Ninguno"


def generate_report() -> Path:
    """Write a local validation report without changing either source file."""
    html_sources = read_html_data(
        DATA_DIR / "followers.html",
        DATA_DIR / "following.html",
    )
    excel_sources = read_follow_data(DATA_DIR / "data_follow.xlsx")

    validations = {}
    for role, parsed in html_sources.items():
        validations[role] = compare_data_sources(
            parsed.data,
            excel_sources[role],
        )

    lines = [
        "# Validación de exportaciones HTML contra Excel",
        "",
        f"Generado localmente: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')}",
        "",
        "Los HTML son la nueva fuente operativa. El Excel se leyó solo como referencia; "
        "no fue modificado.",
        "",
        "| Lista | Filas HTML/Excel | Usuarios únicos H/E | Coincidencias | Faltan en HTML | "
        "Adicionales HTML | Duplicados H/E | Vacíos H/E | Malformados HTML | "
        "Fechas distintas | Perfiles con formato distinto | Identidad de perfil distinta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    labels = {"followers": "Seguidores", "following": "Seguidos"}
    for role, result in validations.items():
        report = html_sources[role].report
        lines.append(
            "| "
            + " | ".join(
                [
                    labels[role],
                    f"{result['html_rows']}/{result['excel_rows']}",
                    f"{result['html_unique_users']}/{result['excel_unique_users']}",
                    str(result["coincidencias"]),
                    str(len(result["faltantes_en_html"])),
                    str(len(result["adicionales_en_html"])),
                    f"{result['duplicados_html']}/{result['duplicados_excel']}",
                    f"{result['usuarios_vacios_html']}/{result['usuarios_vacios_excel']}",
                    str(report["registros_malformados"]),
                    str(len(result["diferencias_de_fecha"])),
                    str(len(result["diferencias_de_formato_de_perfil"])),
                    str(len(result["diferencias_de_identidad_de_perfil"])),
                ]
            )
            + " |"
        )

    for role, result in validations.items():
        report = html_sources[role].report
        lines.extend(
            [
                "",
                f"## {labels[role]}",
                "",
                f"- Bloques HTML detectados: {report['registros_html']}.",
                f"- Filas HTML extraídas: {report['registros_extraidos']}.",
                f"- Registros malformados: {report['registros_malformados']}.",
                f"- Fechas inválidas en HTML: {report['fechas_invalidas']}.",
                f"- Usuarios vacíos: HTML {result['usuarios_vacios_html']}; "
                f"Excel {result['usuarios_vacios_excel']}.",
                f"- Diferencias de escritura de usuario con la misma normalización: "
                f"{len(result['diferencias_de_escritura'])}.",
                f"- Diferencias de fecha: {len(result['diferencias_de_fecha'])}.",
                f"- Perfiles cuya identidad no coincide: "
                f"{len(result['diferencias_de_identidad_de_perfil'])}.",
                "",
                f"**Faltan en HTML** (presentes solo en Excel): "
                f"{_format_names(result['faltantes_en_html'])}.",
                "",
                f"**Solo en HTML** (no aparecen en Excel): "
                f"{_format_names(result['adicionales_en_html'])}.",
                "",
            ]
        )
        date_differences = result["diferencias_de_fecha"]
        if date_differences:
            lines.extend(["### Diferencias de fecha", ""])
            for item in date_differences:
                lines.append(
                    f"- `{item['usuario_normalizado']}`: HTML "
                    f"`{item['fecha_html']}`; Excel `{item['fecha_excel']}`."
                )
            lines.append("")

        format_differences = result["diferencias_de_formato_de_perfil"]
        lines.extend(
            [
                f"Los enlaces de perfil tienen distinta representación textual en "
                f"{len(format_differences)} registros; esto no cuenta como discrepancia "
                "de cuenta cuando ambas URLs se resuelven al mismo usuario.",
                "",
            ]
        )

    lines.extend(
        [
            "## Evaluación",
            "",
            "Los nombres de usuario normalizados, las fechas disponibles y la identidad "
            "de las cuentas se comparan por separado. Las diferencias de formato de URL "
            "del export se conservan en este reporte y no se usan como diferencias de "
            "identidad.",
            "",
            "En la aplicación los enlaces se presentan en forma canónica "
            "`https://www.instagram.com/{usuario}` tras validar el dominio y el "
            "identificador. En particular, el HTML de seguidos utiliza enlaces internos "
            "con la ruta `/_u/{usuario}`; esa representación se conserva como dato de "
            "origen y se normaliza para la tabla.",
            "",
        ]
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return REPORT_PATH


if __name__ == "__main__":
    print(generate_report())

#!/usr/bin/env bash
set -euo pipefail

INVENTORY_DIR="data/raw/inventory/Forest_Inventory_Brazil_2007_1-20260505_010726"
OUTPUT_DIR="data/processed/01_kml"

mkdir -p "$OUTPUT_DIR"

count=0
for kmz in "$INVENTORY_DIR"/*.kmz; do
    name=$(basename "$kmz" .kmz)
    unzip -p "$kmz" doc.kml > "$OUTPUT_DIR/${name}.kml"
    echo "Extraído: ${name}.kml"
    count=$((count + 1))
done

echo ""
echo "Concluído: $count arquivos KML extraídos em $OUTPUT_DIR"

#!/bin/bash

# Script de inicialização rápida

echo "🚀 Iniciando Projefarma - Sistema 100% Precisão"
echo ""

# Verifica Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 não encontrado"
    exit 1
fi

# Verifica .env
if [ ! -f ".env" ]; then
    echo "⚠️  Arquivo .env não encontrado"
    echo "   Criando a partir de .env.example..."
    cp .env.example .env
    echo "   ⚠️  IMPORTANTE: Edite .env e adicione sua chave OpenAI"
    echo ""
fi

# Verifica dependências
echo "📦 Verificando dependências..."
pip install -q -r requirements.txt

# Cria diretórios necessários
mkdir -p uploads debug resultados

# Inicia aplicação
echo ""
echo "✅ Iniciando servidor..."
echo "🌐 Acesse: http://localhost:5000"
echo ""

python3 app.py

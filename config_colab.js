// Configurações de conexão para o treinamento via Google Colab (Temporário para testes)
process.env.VLM_URL = 'https://old-gifts-stay.loca.lt/v1/chat/completions';
process.env.VLM_MODEL = 'qwen2.5-vl';
process.env.VLM_TIMEOUT = '300000'; // 5 minutos para evitar timeouts em modelos pesados
process.env.VLM_MAX_TOKENS = '6144';

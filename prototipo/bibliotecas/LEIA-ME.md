# Bibliotecas externas

Esta pasta recebe o `nvdaControllerClient.dll`, usado por
`analisador/nvda` para enviar texto ao NVDA. A DLL **nao** vai para o git
(ver `.gitignore`): ela e distribuida pelo NV Access sob LGPL 2.1.

## Como obter

1. Baixe o arquivo que termina em `controllerClient.zip` na pasta de versoes
   do NVDA (o readme oficial tem o link "Latest stable"):
   https://github.com/nvaccess/nvda/blob/master/extras/controllerClient/readme.md
2. Extraia o zip. Ele traz uma pasta por arquitetura.
3. Copie o `nvdaControllerClient.dll` da pasta que combina com o **Python**
   (nao com o Windows): `x64` para Python de 64 bits, `x86` para 32 bits,
   `arm64` para Python ARM. Para ver:
   `python -c "import struct,platform;print(struct.calcsize('P')*8, platform.machine())"`
4. Cole nesta pasta, ao lado deste arquivo. Tambem vale
   `bibliotecas/x64/nvdaControllerClient.dll`.

Para usar a DLL de outro lugar: `--dll caminho` ou a variavel de ambiente
`NVDA_CONTROLLER_DLL`.

from datetime import datetime
from models.logger import Log

log = Log()
hora_atual = datetime.now().hour

from Coleta_AWS         import ColetaAWS
from Coleta_GoogleCloud import executar as executar_google
from Coleta_OEM         import coletaOEM
from Coleta_OntapNetapp import coletaNetapp
from Coleta_Vmware      import executar as executar_vmware
from Coleta_OracleCloud import coletaOci
from coleta_de_tabelas  import coletatabelas
from network_intragov   import coletanetworkintragov
from network_prodesp    import coletanetworkprodesp


## ─── Configuração de horários ────────────────────────────────────────────────
## Ajuste as horas conforme sua necessidade
AGENDA2 = {4,7,22}
AGENDA3 = {4,14,20}

log.logmessage('**************************** INICIO DO PROCESSO ****************************')
## NetApp e VMware rodam toda hora — sem filtro
## ─────────────────────────────────────────────────────────────────────────────
##pyinstaller --onefile --noconsole --icon=icone.ico cloudpulse.py

if hora_atual in AGENDA3:
    log.logmessage('*** [INICIO] : ORACLE CLOUD')
    coletaOci()
    log.logmessage('*** [FIM]    : ORACLE CLOUD')
else:
    log.logmessage(f'*** [IGNORADO] : ORACLE CLOUD (hora {hora_atual} fora do agendamento)')

log.logmessage('*** [INICIO] : NETAPP ONTAP')
coletaNetapp()
log.logmessage('*** [FIM]    : NETAPP ONTAP')

log.logmessage('*** [INICIO] : VMWARE')
executar_vmware()
log.logmessage('*** [FIM]    : VMWARE')

if hora_atual in AGENDA3:
    log.logmessage('*** [INICIO] : GOOGLE CLOUD')
    executar_google()
    log.logmessage('*** [FIM]    : GOOGLE CLOUD')
else:
    log.logmessage(f'*** [IGNORADO] : GOOGLE CLOUD (hora {hora_atual} fora do agendamento)')

log.logmessage('*** [INICIO] : ORACLE ENTERPRISE MANAGER')
coletaOEM()
log.logmessage('*** [FIM]    : ORACLE ENTERPRISE MANAGER')

if hora_atual in AGENDA3:
    log.logmessage('*** [INICIO] : AWS EC2')
    ColetaAWS()
    log.logmessage('*** [FIM]    : AWS EC2')
else:
    log.logmessage(f'*** [IGNORADO] : AWS EC2 (hora {hora_atual} fora do agendamento)')

if hora_atual in AGENDA2:
    log.logmessage('*** [INICIO] : COLETA TABELAS')
    coletatabelas()
    log.logmessage('*** [FIM]    : COLETA TABELAS')
else:
    log.logmessage(f'*** [IGNORADO] : COLETA TABELAS (hora {hora_atual} fora do agendamento)')

if hora_atual in AGENDA2:
    log.logmessage('*** [INICIO] : NETWORK INTRAGOV')
    coletanetworkintragov()
    log.logmessage('*** [FIM]    : NETWORK INTRAGOV')
else:
    log.logmessage(f'*** [IGNORADO] : NETWORK INTRAGOV (hora {hora_atual} fora do agendamento)')

if hora_atual in AGENDA2:
    log.logmessage('*** [INICIO] : NETWORK PRODESP')
    coletanetworkprodesp()
    log.logmessage('*** [FIM]    : NETWORK PRODESP')
else:
    log.logmessage(f'*** [IGNORADO] : NETWORK PRODESP (hora {hora_atual} fora do agendamento)')

log.logmessage('**************************** FIM DO PROCESSO ****************************')
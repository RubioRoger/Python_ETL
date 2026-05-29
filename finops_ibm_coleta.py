# ===============================
# EXECUÇÃO IBM BILLING
# pyinstaller --onefile --noconsole finops_ibm_coleta.py
# pip uninstall shared-scr -y
# pip install -e C:\scr 
# pip install --upgrade shared-scr
# pyinstaller finops_ibm_coleta.py --noconsole --onefile --collect-all scr
#Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
#Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
#Remove-Item *.spec -ErrorAction SilentlyContinue
#pyinstaller finops_ibm_coleta.py --onefile --noconsole --collect-all scr --collect-all ibm_cloud_sdk_core --collect-all ibm_platform_services --collect-all ibm_watson --hidden-import=pyodbc
#pyinstaller etl_finops.py --onefile --noconsole --collect-all scr --collect-all ibm_cloud_sdk_core --collect-all ibm_platform_services --collect-all ibm_watson --hidden-import=pyodbc
#pyinstaller etl_finops.py --onefile --noconsole --collect-all scr --collect-all unidecode --collect-all office365 --collect-all ibm_cloud_sdk_core --collect-all ibm_platform_services --collect-all ibm_watson --hidden-import pyodbc
# ===============================
# ===============================
# EXECUÇÃO IBM BILLING
# ===============================

from datetime import datetime
import pandas as pd

from models.app import App
from models.ibm_projeto import IBM
from models.database import DataBase
from models.logger import Log

log = Log()

# ===============================
# FUNÇÃO PARA GERAR MESES
# ===============================
class finops_ibm:
        

        def gerar_meses_execucao():
            hoje = datetime.now()
        
            # mês atual
            mes_atual = hoje.replace(day=1)
        
            # mês anterior
            if mes_atual.month == 1:
                mes_anterior = mes_atual.replace(year=mes_atual.year - 1, month=12)
            else:
                mes_anterior = mes_atual.replace(month=mes_atual.month - 1)
        
            return [mes_atual, mes_anterior]
        
        
        def formatar_billing_month(data):
            billing_month_api = data.strftime("%Y-%m")
            billing_month_col = data.strftime("%Y-%m-01")
            return billing_month_api, billing_month_col
        
        
        # ===============================
        # EXECUÇÃO
        # ===============================
        
        app = App()
        dbo = DataBase()
        
        keys = [
            {
                "cliente": "DIPOL",
                **app.api_ibm_dipol()
            },
            {
                "cliente": "SGGD",
                **app.api_ibm_sggd()
            }
        ]
        
        meses_execucao = gerar_meses_execucao()
        
        dfs_gerais = []
        
        for data_mes in meses_execucao:
        
            billing_month_api, billing_month_col = formatar_billing_month(data_mes)
        
            log.logmessage(f"[PROCESSANDO] {billing_month_col}")
        
            for key in keys:
                ibm = IBM(key, billing_month_api, billing_month_col)
                df = ibm.coletar()
                dfs_gerais.append(df)
        
        
        df_final = pd.concat(dfs_gerais, ignore_index=True)
        
        log.logmessage("[FINAL] DATAFRAME CONSOLIDADO")
        
        
        # ===============================
        # BANCO DE DADOS
        # ===============================
        
        key_db = app.key_db('fin')
        
        dbo.conectar(key_db)
        
        dbo.organizar_df('ibm_billing_cost', df_final)
        
        # DELETE controlado por cliente + mês
        df_delete = df_final[['cliente', 'billing_month']].drop_duplicates()
        
        dbo.deletar_informacoes('ibm_billing_cost', df_delete)
        
        dbo.inserir_df('ibm_billing_cost', df_final)
        
        dbo.desconectar()
        
        log.logmessage("[PROCESSO FINALIZADO]")

if __name__ == "__main__":
    finops_ibm()
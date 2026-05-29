from models.sharepoint import SharePoint
from models.app import App
from models.database import DataBase
from models.configuracoes import Config
import numpy as np
from datetime import datetime
cfg = Config()

class finops_aws:
    def __init__(self):
    
        app = App()
        dbo = DataBase()
        
        key = app.key_db('fin')
        
        #cfg.cfg_proxy()
        sha = SharePoint(fin=True)
        
        hoje = datetime.today()
        
        mes_atual = f"{hoje.month}_{hoje.year}"
        
        if hoje.month == 1:
            mes_anterior = f"12_{hoje.year - 1}"
        else:
            mes_anterior = f"{hoje.month - 1}_{hoje.year}"
        
        lista = [mes_atual, mes_anterior]
        
        
        for i in lista:
            df = sha.ler_arquivos('Documents/AWS/AWS',i)
            print(df)
            df = df.replace({np.nan: None})
            
            print(df)
            try:
                dbo.conectar(key)
                
                dbo.organizar_df('aws_billing_cost', df)
                
                # DELETE controlado por cliente + mês
                try:
                    df_delete = df[['BillingPeriodStartDate', 'InvoiceID','PayerAccountId']].drop_duplicates()
                except: pass
    
                dbo.deletar_informacoes('aws_billing_cost', df_delete)
                
                dbo.inserir_df('aws_billing_cost', df)
                
                dbo.desconectar()
            except : dbo.desconectar()
            #log.logmessage("[PROCESSO FINALIZADO]")
            
if __name__=="__main__":
    finops_aws()
from models.sharepoint import SharePoint
from models.app import App
from models.database import DataBase
import numpy as np
from datetime import datetime
import pandas as pd

class finops_aws_auditoria:
    def __init__(self):
    
        app = App()
        dbo = DataBase()
        
        key = app.key_db('fin')
        
        sha = SharePoint(fin=True)
        
        df = sha.ler_auditoria('Documents/AWS/Auditoria')
        df = pd.DataFrame(df)
        df = df.drop_duplicates()
        df['valor'] = df['valor'].round(15).astype(str).str.replace('.', ',', regex=False)
        df['valor'] = df['valor'].astype(str).str.replace('nan', '0', regex=False)
        df['valor'] = df['valor'].round(15).astype(str).str.replace(',', '.', regex=False)
        df = df.replace({np.nan: None})

        df.to_excel('auditoria.xlsx',index=False)
        dbo.conectar(key)
        dbo.organizar_df('aws_auditoria_billing_cost',df)
        dbo.executar('delete from aws_auditoria_billing_cost')
        dbo.inserir_df('aws_auditoria_billing_cost',df)
        dbo.desconectar()

            
if __name__=="__main__":
    finops_aws_auditoria()
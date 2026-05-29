from models.sharepoint import SharePoint
from models.app import App
from models.database import DataBase
from models.configuracoes import Config
import numpy as np
import pandas as pd
from time import sleep
from decimal import Decimal

class finops_oracle:

    def __init__(self):
    
        app = App()
        dbo = DataBase()
        
        key = app.key_db('fin')
        
        sha = SharePoint(fin=True)
        
        lista = sha.listar_pastas('Documents/Oracle')
        
        dfs = []

        for i in lista:

            df = sha.ler_oracle(f'Documents/Oracle/{i}')

            if df.empty:
                continue

            # cria coluna projeto com o nome da pasta
            df["projeto"] = i

            dfs.append(df)

        if dfs:
            df = pd.concat(dfs, ignore_index=True)
        else:
            df = pd.DataFrame()

        if not df.empty:

            # tratamento da data
            df["data"] = pd.to_datetime(df["data"], format="%b %d %Y", errors="coerce")
            df["data"] = df["data"].dt.strftime("%Y-%m-%d")

            # limpeza básica
            df["produto"] = df["produto"].astype(str).str.strip()
            df["servico"] = df["servico"].astype(str).str.strip()
            df["valor"] = df["valor"].astype(str).str.strip()
            df["projeto"] = df["projeto"].astype(str).str.strip()

            # coluna auxiliar para identificar duplicidade
            df["_concat"] = (
                df["data"].astype(str) + "|" +
                df["produto"].astype(str) + "|" +
                df["servico"].astype(str) + "|" +
                df["valor"].astype(str) + "|" +
                df["projeto"].astype(str)
            )

            # remove duplicados
            df = df.drop_duplicates(subset="_concat")

            # remove coluna auxiliar
            df = df.drop(columns="_concat")
            # Lógica de padronização da coluna 'valor'
            # Converte para string e limpa espaços
            df['valor'] = df['valor'].astype(str).str.replace('.', ',', regex=False)
            df['valor'] = df['valor'].astype(str).str.replace('nan', '0', regex=False)
            df['valor'] = df['valor'].astype(str).str.replace(',', '.', regex=False)
            df['valor'] = df['valor'].astype(float)

            df = df.replace({np.nan: None})
        #try:
        #    df.to_csv('teste.csv', index=False, sep=';')
        #except: 
        #    print('************** FECHE O ARQUIVO **************')
            #sleep(7)
            #df.to_csv('teste.csv', index=False, sep=';')

        dbo.conectar(key)
        dbo.organizar_df('oracle_billing_cost', df)
        
        dbo.executar('delete from oracle_billing_cost',commit=True)
        
        dbo.inserir_df('oracle_billing_cost', df)
        
        dbo.desconectar()


if __name__=="__main__":
    finops_oracle()
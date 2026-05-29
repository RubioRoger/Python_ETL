from models.database import DataBase
from models.app import App
from models.sharepoint import SharePoint
from models.configuracoes import Config
from models.logger import Log
from datetime import datetime, timedelta
import math

log = Log()
conf = Config()

data_inicio = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')


app = App()

key = app.key_db('cap')

dbo = DataBase()

#  pyinstaller 05-migracao/coleta_de_tabelas.py --onefile --noconsole --collect-all models --collect-all unidecode --collect-all office365  --hidden-import pyodbc
################################################################################################################## forecast
log.logmessage('--------------------------------- inicio do processo ---------------------------------')
class coletatabelas():
    def part1(self):
        self.sha.criar_pasta('migracao','Documents/etl_capacity')

        lista = [
        'tb_google_forecast',
        'tb_azure_forecast_all_servers',
        'tb_aws_forecast_all_servers',
        'tb_oem_forecast',
        'tb_forecast_relatorio_parcial_servidores',
        'tb_cpit_cptm_forecast_2_link_mes',
        'tb_cpit_cptm_forecast_5_storage_interpolado',
        'tb_cpit_cptm_forecast_2_vc_interpolado',
        'tb_cpit_cptm_forecast_4_host_interpolado',
        'tb_cpit_cptm_forecast_1_vm_interpolado',
        'tb_forecast_relatorio_parcial_servidores',
                ]
        
        dbo.conectar(key) 
        for i in lista:
            try:
                df = dbo.consulta_dataframe(f"""select * from {i} where data >= '{data_inicio}' """)
                self.sha.exportar_csv_sem_data(df=df,tabela=i,remote_folder='Documents/etl_capacity/outputs')
                #df.to_csv(f'outputs/{i}.csv',index=False, encoding='UTF-8',sep=';')
                log.logmessage(f'Arquivo {i} Salvo com sucesso')
            except: print(f'Não foi possivel salvar o arquivo {i}')
        dbo.desconectar()

    def part2(self):
        lista = [
        'tb_vcenter_forecast'
                ]
        
        dbo.conectar(key)
        tamanho = 1000000
        for i in lista:
            #try:
                df = dbo.consulta_dataframe(f"""select * from {i} where data >= '{data_inicio}' """)
                #sha.exportar_csv_sem_data(df=df,tabela=i,remote_folder='Documents/etl_capacity/outputs')
                
                divisao = math.ceil(len(df)/tamanho)
                for n in range(divisao):
                    ini = n * tamanho
                    fim = ini + tamanho
                    df_p = df.iloc[ini:fim]
                    #df_parte.to_csv(f"arquivo_parte_{n+1}.csv", index=False)
                    nome_arquivo = f'{i}-{n+1}'
                    
                    #df_p.to_csv(f'outputs/{nome_arquivo}',index=False, encoding='UTF-8',sep=';')
                    self.sha.exportar_csv_sem_data(df=df_p,tabela=(nome_arquivo),remote_folder='Documents/etl_capacity/outputs')
                    #sha.coletar_arquivos(pasta_sharepoint='Documents/etl_capacity/migracao',pasta_local='outputs')
                log.logmessage(f'Arquivo {i} Salvo com sucesso')
            # except: print(f'Não foi possivel salvar o arquivo {i}')
        
        dbo.desconectar()
        log.logmessage('--------------------------------- Fim do processo ---------------------------------')


    def __init__(self):
        self.sha = SharePoint()
        self.sha.deletar_arquivo(caminho_arquivo='Documents/etl_capacity/outputs')
        self.part1()
        self.part2()
        #sha.enviar_arquivos(pasta_sharepoint='Documents/etl_capacity/outputs',pasta_local='outputs')


if __name__=='__main__':
    coletatabelas()
        
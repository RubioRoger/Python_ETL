#from models.Auxiliar import App, DataBase, Log, Config, SharePoint

#from models.tabelas           import Intragov  # TABELAS DO BANCO DE DADOS
from models.sharepoint        import SharePoint    # TRATATIVAS DO SHAREPOINT
from models.configuracoes     import Config        # CONFIGURAÇÕES BASICAS
from models.logger            import Log           # GERAR ARQUIVO DE LOG
from models.database          import DataBase      # BANCO DE DADOS
from models.app               import App           # ARQUIVO APP.CONFIG
from glob                     import glob
import pandas                 as pd
import numpy                  as np

# INSTANCIAS DO MODELS
#intra    = Intragov()              
lg       = Log()                       
cf       = Config()                    
db       = DataBase()                  
ap       = App()


db_key   = ap.key_db('cap')
#tabela   = intra.tb_cptm_intragov_network_mes() # TABELA PRINCIPAL
#view     = intra.vw_cptm_intragov_network_mes() # VIEW PARA FORECAST

class coletanetworkintragov():

# REALIZA A EXTRAÇÃO DOS ARQUIVOS CSV DA PASTA ARQUIVOS
    def extract(self):
        lista_tabela = []
        lg.logmessage('Lendo arquivos de network')
    
        colunas = [f'col{i}' for i in range(1, 17)]
        file_list = glob(r"./network/*CPTM*.csv")
    
        for tabela in file_list:
            with open(tabela, 'r', encoding='utf-8') as f:
                mes_info = None
                traffic_line = None
    
                for i, linha in enumerate(f):
                    if mes_info is None and linha.strip().startswith('# Start:'):
                        temp_info = linha.split('# Start:')[1].strip()
                        mes_info = temp_info.split(';')[0].strip()
    
                    if traffic_line is None and '- Traffic -' in linha:
                        traffic_line = i
    
                    if mes_info and traffic_line is not None:
                        break

            df_temp = pd.read_csv(tabela, header=traffic_line - 1, sep=";", names=colunas)
            df_temp['data_coleta'] = mes_info
            lista_tabela.append(df_temp)
    
        df = pd.concat(lista_tabela, ignore_index=True)
    
        df.columns = [cf.cfg_config_header(col) for col in df.columns]

        df.rename(columns={
            'COL1': 'network',
            'COL8': 'last_in',
            'COL9': 'avg_in',
            'COL10': 'max_in',
            'COL11': 'in_util_perc',

            'COL12': 'last_out',
            'COL13': 'avg_out',
            'COL14': 'max_out',
            'COL15': 'out_util_perc',

        }, inplace=True)

        colunas_convert = ['last_in', 'avg_in', 'max_in', 'last_out', 'avg_out', 'max_out','out_util_perc','in_util_perc']
        for col in colunas_convert:
            df[col] = df[col].apply(cf.cfg_convert_to_kb)
        
        for col in colunas_convert:
            df[col] = df[col].apply(cf.cfg_convert_to_kb).astype(str)

        for col in colunas_convert:
            df[col] = (
                df[col]
                .apply(cf.cfg_convert_to_kb)   # sua conversão
                .astype(str)                   # vira string
                .replace("nan", None)
                .str.replace(r"[^0-9.\-]", "", regex=True)
            )

        df.drop(df.columns[[1,2,3,4,5,6,15]], axis=1, inplace=True)
        df['id_tab']  = df['network'].astype(str)+df['DATA_COLETA']
        df['id_tab']  = df['id_tab'].replace('/','',regex=True).replace('-','',regex=True)

        #print(df.iloc[584])
        #sp.deletar_arquivo()
        #sp.salvar_arquivo(df,"Documents/etl_capacity/intragov/network")

        df = df.replace({np.nan: None})
        df = df.drop_duplicates()

        return df

# INSERI INFORMAÇÕES NO BANCO DE DADOS E MIGRA OS ARQUIVOS DA PASTA ARQUIVOS PARA A PASTA OUTPUTS
    def insert(self):

        df  = self.extract()

        df2 = df[['id_tab']]

        db.conectar(db_key)

        db.executar(tabela,commit=True)

        db.organizar_df('tb_cptm_network_mes',df)

        db.deletar_informacoes('tb_cptm_network_mes',df2)

        db.inserir_df('tb_cptm_network_mes',df)

        db.executar(view,commit=True)

        db.desconectar()

# EXECUTAS AS FUNÇÕES DO PROCESSO
    def __init__(self):
        #Config.versionar_codigo(__file__)
        sha       = SharePoint()
        try:
            sha.criar_pasta("etl_capacity"  , parent_path="Documents")
            sha.criar_pasta("cptm"          , parent_path="Documents/etl_capacity")
            sha.criar_pasta("network"       , parent_path="Documents/etl_capacity/cptm")
        except: lg.logmessage('[ERRO] : PROBLEMAS REFERENTE A SHAREPOINT')

        try:
            self.insert()
        except: 
            lg.logmessage('[ERRO] : PROBLEMAS COM A INSERCAO DAS INFORMACOES NO BANCO DE DADOS')
            try:
                db.desconectar()
            except: pass

        try:
            cf.cfg_mover_csv_outputs()
        except: lg.logmessage('[ERRO] : PROBLEMAS NA MIGRACAO DOS ARQUIVOS PARA A PASTA OUTPUTS')

if __name__ == '__main__':
    coletanetworkintragov()



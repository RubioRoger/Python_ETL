import pandas as pd

from models.app import App
from models.database import DataBase
from models.logger import Log
from models.configuracoes import Config
from models.sharepoint import SharePoint

from glob import glob

lg = Log()
cf = Config()
db = DataBase()
ap = App()

db_key = ap.key_db('cap')

sp = SharePoint()

class Intragov():

    # fonte sharepoint
    def coleta_sharepoint(self):
        sp.coletar_arquivos('Documents/etl_capacity/diorama/intragov/link','arquivos')

    def extract_inventario(self):
        lg.logmessage('Lendo arquivos de invnetario')

        file_list = glob(r"./arquivos/PAC_PBI.xlsx")
        lg.logmessage('arquivo localizado')
    
        # Processa cada arquivo
        for tabela in file_list:
            inventario = pd.read_excel(tabela)  # Define os nomes fixos ao ler
        
        inventario.columns = [cf.cfg_config_header(col) for col in inventario.columns]
        
        inventario = inventario[['ID_UNIDADE','BANDA_NOMINAL','REDUNDANCIA_ACESSO_SIMNAO','ORGAO_SIGNATARIO','ENTIDADE_DE_INSTALACAO','LOCALIDADEMUNICIPIO_INSTALACAO',
                                'ICMS','SCM','SAI','STI','TOTAL'
                                ]]
        inventario['BANDA_NOMINAL'] = inventario['BANDA_NOMINAL']
        inventario['id'] = inventario['ID_UNIDADE'].str.split('/').str[0].astype(int).astype(str)

        colunas = [
            'REDUNDANCIA_ACESSO_SIMNAO',
            'ORGAO_SIGNATARIO',
            'ENTIDADE_DE_INSTALACAO',
            'LOCALIDADEMUNICIPIO_INSTALACAO'
        ]
        
        for col in colunas:
            inventario[col] = inventario[col].apply(cf.cfg_remove_acentos)

        self.inventario = inventario

    def extract_links(self):
        lista_tabela = []
        lg.logmessage('Lendo arquivos de links')
    
        colunas = [f'col{i}' for i in range(1, 17)]
        file_list = glob(r"./arquivos/*CPTM.csv")
    
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
    
        lg.logmessage('Unificando arquivos')
        df = pd.concat(lista_tabela, ignore_index=True)
    
        df.columns = [cf.cfg_config_header(col) for col in df.columns]
    
        df.drop(df.columns[[1, 2, 3, 4, 5, 6, 15]], axis=1, inplace=True)
    
        df.rename(columns={
            'COL1': 'link',
            'COL8': 'last_in',
            'COL9': 'avg_in',
            'COL10': 'max_in',
            'COL11': 'last_out',
            'COL12': 'avg_out',
            'COL13': 'max_out',
            'COL14': 'overall_out',
            'COL15': 'overall_in',
        }, inplace=True)
    
        df[['id', 'ip']] = df['link'].str.extract(r'_(\d+)_.*? - Traffic - ([\d\.]+)')
        df = df.replace('', '0').fillna('0')
    
        colunas_convert = ['last_in', 'avg_in', 'max_in', 'last_out', 'avg_out', 'max_out', 'overall_out', 'overall_in']
        for col in colunas_convert:
            df[col] = df[col].apply(cf.cfg_convert_to_kb)
    
        # Join com inventario
        lg.logmessage('Cruzamento com a planinha de inventário')
        df = df.merge(
            self.inventario[['id', 'ID_UNIDADE', 'BANDA_NOMINAL','REDUNDANCIA_ACESSO_SIMNAO','ORGAO_SIGNATARIO','ENTIDADE_DE_INSTALACAO','LOCALIDADEMUNICIPIO_INSTALACAO'
                            ,'ICMS','SCM','SAI','STI','TOTAL']],how='left',on='id')
        
        lg.logmessage('Tratando colunas')
        df['link']                                = df['link'].str.split(' - Traffic -').str[0]
        df['ID_UNIDADE']                          = df['ID_UNIDADE']                           .replace('', '000000/00').fillna('000000/00')
        df['BANDA_NOMINAL']                       = df['BANDA_NOMINAL']                        .replace('', '0').fillna('0')
        df['REDUNDANCIA_ACESSO_SIMNAO']           = df['REDUNDANCIA_ACESSO_SIMNAO']            .replace('', 'N/D').fillna('N/D')
        df['ORGAO_SIGNATARIO']                    = df['ORGAO_SIGNATARIO']                     .replace('', 'N/D').fillna('N/D')
        df['ENTIDADE_DE_INSTALACAO']              = df['ENTIDADE_DE_INSTALACAO']               .replace('', 'N/D').fillna('N/D')
        df['LOCALIDADEMUNICIPIO_INSTALACAO']      = df['LOCALIDADEMUNICIPIO_INSTALACAO']       .replace('', 'N/D').fillna('N/D')
        df['ICMS']                                = df['ICMS']                                 .replace('', 'N/D').fillna('N/D')
        df['SCM']                                 = df['SCM']                                  .replace('', 0).fillna(0)
        df['SAI']                                 = df['SAI']                                  .replace('', 0).fillna(0)
        df['STI']                                 = df['STI']                                  .replace('', 0).fillna(0)
        df['TOTAL']                               = df['TOTAL']                                .replace('', 0).fillna(0)
        df['id_tab']  = df['id'].astype(str)+df['ip']+df['DATA_COLETA']
        df['id_tab']  = df['id_tab'].astype(str).replace('/','',regex=True).replace('-','',regex=True)
        df['id_tab'] = df['id_tab'].replace(r'\.', '', regex=True)
        #df.to_excel('meu_teste.xlsx',index=False)
        df['in_util_perc'] = df.apply(lambda row: 0 if row['BANDA_NOMINAL'] in [0, '', '0'] else (float(row['avg_in']) / float(row['BANDA_NOMINAL'])) * 100,
                axis=1)
        df['out_util_perc'] = df.apply(lambda row: 0 if row['BANDA_NOMINAL'] in [0, '', '0'] else (float(row['avg_out']) / float(row['BANDA_NOMINAL'])) * 100,
                axis=1)
        
        self.df = df

    def insert_links(self):
        lg.logmessage('Inserindo informações no banco de dados')
        df = self.df
        df.columns = [cf.cfg_lower_header(col) for col in df.columns]
        df = df.drop(columns=['id_unidade'])
        df = df.rename(columns={
            'redundancia_acesso_simnao': 'redundancia',
            'entidade_de_instalacao': 'entidade',
            'localidademunicipio_instalacao':'localidade',
            'scm': 'smc'})

        db.executar(f'''
            IF OBJECT_ID('dbo.tb_cptm_intragov_link_mes', 'U') IS NULL
            BEGIN
            CREATE TABLE dbo.tb_cptm_intragov_link_mes(
            id_tab                nvarchar(30) primary key,
            id	                  nvarchar(20),
            ip	                  nvarchar(30),
            link	              nvarchar(150),
            redundancia           nvarchar(10),
            orgao_signatario      nvarchar(100),
            entidade              nvarchar(120),
            localidade            nvarchar(60),
            data_coleta           date,
            banda_nominal         float,
            last_in	              float,
            avg_in	              float,
            max_in	              float,
            last_out	          float,
            avg_out	              float,
            max_out	              float,
            overall_out	          float,
            overall_in	          float,
            in_util_perc          float,
            out_util_perc         float,
            icms                  nvarchar(10),
            smc  	              float,
            sai  	              float,
            sti  	              float,
            total  	              float
            )end
                ''',commit=True)

        db.organizar_df(f'tb_cptm_intragov_link_mes',df)
    
        db.deletar_id(f'tb_cptm_intragov_link_mes',df)
        
        df = df.drop_duplicates(subset=['id_tab'])
    
        db.inserir_df(f'tb_cptm_intragov_link_mes',df)

    def view_intragov(self):
        db.executar('''
                    IF OBJECT_ID('dbo.vw_cptm_intragov_link_mes', 'V') IS NULL
                    BEGIN
                    exec('create view vw_cptm_intragov_link_mes as
                    select  
                    link SERVIDOR,
                    DATA_COLETA,
                    IN_UTIL_PERC,
                    OUT_UTIL_PERC
                    from tb_cptm_intragov_link_mes
                    ')end
                    ''')
        lg.logmessage('[SUCESSO] : VIEW vw_cptm_intragov_link_mes criada')

    def __init__(self):
        #try:
            self.coleta_sharepoint()

            
            self.extract_inventario()
            self.extract_links()
            self.insert_links()
            #cf.cfg_mover_csv_outputs()
            #self.view_intragov()
        #except:
        #    lg.logmessage('[ERRO INTRAGOV] : Processo nao executado')

db.conectar(db_key)
Intragov()
db.desconectar()

# pyinstaller --onefile --noconsole links.py

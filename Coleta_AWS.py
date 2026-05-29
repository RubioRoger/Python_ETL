#pyinstaller --onefile --noconsole Coleta_AWS.py

import warnings
warnings.filterwarnings('ignore')

from models.app import App
from models.configuracoes import Config
from models.logger import Log
from models.sharepoint import SharePoint

import boto3
import pandas as pd
from datetime import datetime, timedelta
st = datetime.now()
data_file = st.strftime("%Y-%m-%d_%H_00_00")

#data_ref = "2025-07-29"
data_ref = st.strftime("%Y-%m-%d")

lg = Log()
cfg = Config()
app = App()

#sha = SharePoint()

class ColetaAWS():

    def metricas(self, cloudwatch, namespace, metric_name, dimensions):
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=30) ##################################################################################### seleção de dias
        all_datapoints = []

        current_time = start_time
        while current_time < end_time:
            next_hour = current_time + timedelta(hours=1)
            try:
                response = cloudwatch.get_metric_statistics(
                    Namespace=namespace,
                    MetricName=metric_name,
                    Dimensions=dimensions,
                    StartTime=current_time,
                    EndTime=next_hour,
                    Period=3600,
                    Statistics=["Average"]
                )
                datapoints = response.get("Datapoints", [])
                if datapoints:
                    for point in datapoints:
                        all_datapoints.append(
                            (round(point["Average"], 2), point["Timestamp"])
                        )
            except Exception as e:
                lg.logmessage(f"[ERRO] : Falha ao coletar {metric_name} para {dimensions[0]['Value']} -> {e}")
            current_time = next_hour

        return all_datapoints

    def coleta_vm(self):
        
        lg.logmessage('[INICIO] : REALIZANDO COLETA AWS EC2')

        memorias = {
            "t3a.xlarge": 16384, "t3a.large": 8192, "r5a.2xlarge": 65536,
            "r5a.4xlarge": 131072, "t3a.2xlarge": 32768, "t3a.medium": 4096,
            "i3en.6xlarge": 196608, "r5a.xlarge": 32768, "c5n.xlarge": 10752,
            "m6a.xlarge": 16384, "m6a.2xlarge": 32768, "t3.large": 8192,
            "x2iedn.xlarge": 102400
        }

        lista = app.aws_list().split(',')
        linhas = []
        contador = 0

        for cliente in lista:
            try:
                lg.logmessage(f'[CLIENTE] : {cliente}')
                api_key = app.key_aws(cliente)

                args_conexao = {
                    'region_name': 'sa-east-1',
                    'aws_access_key_id': api_key["key_id"],
                    'aws_secret_access_key': api_key["access_key"],
                    'verify': False
                }

                ec2 = boto3.client('ec2', **args_conexao)
                cloudwatch = boto3.client('cloudwatch', **args_conexao)

                resposta = ec2.describe_instances()

                for reserva in resposta['Reservations']:
                    for instancia in reserva['Instances']:
                        contador += 1
                        date_process = datetime.now()
                
                        instance_id = instancia['InstanceId']
                        nome_instancia = next(
                            (tag['Value'] for tag in instancia.get('Tags', []) if tag['Key'] == 'Name'),
                            None
                        )
                
                        # Nome da chave (KeyName pode estar ausente, então usamos .get)
                        nome_chave = instancia.get('KeyName', None)
                        
                        # Nome(s) do(s) grupo(s) de segurança
                        grupos_seguranca = instancia.get('SecurityGroups', [])
                        nomes_grupos_seguranca = ', '.join([sg['GroupName'] for sg in grupos_seguranca]) if grupos_seguranca else None

                        lg.logmessage(
                            f'[COLETA] : num vm = {contador}, vm = {instance_id}, nome = {nome_instancia}, datetime = {date_process}'
                        )
                
                        if instancia['State']['Name'] != 'running':
                            continue
                
                        vm_size = instancia['InstanceType']
                        dimensions = [{'Name': 'InstanceId', 'Value': instance_id}]

                        cpu_metrics = self.metricas(cloudwatch, "AWS/EC2", "CPUUtilization", dimensions)
                        mem_metrics = self.metricas(cloudwatch, "CWAgent", "Memory % Committed Bytes In Use", dimensions)
                        disk_metrics = self.metricas(cloudwatch, "CWAgent", "LogicalDisk % Free Space", dimensions)

                        for cpu_value, timestamp in cpu_metrics:
                            mem_value = next((val for val, ts in mem_metrics if ts == timestamp), None)
                            disk_value = next((val for val, ts in disk_metrics if ts == timestamp), None)

                            memory_mb = memorias.get(vm_size, 0)
                            memory_gb = memory_mb // 1024

                            linha = {
                                "instance_id": instance_id,
                                "nome_instancia": nome_instancia,
                                "nome_chave":nome_chave,
                                "grupo":nomes_grupos_seguranca,
                                "cliente": cliente,
                                "data_coleta": timestamp,
                                "vm_size": vm_size,
                                "cpu_percent_use": cpu_value,
                                "memoria_use": mem_value,
                                "disk_free": disk_value,
                                "memoria_disp": memory_gb,
                            }
                            linhas.append(linha)

            except Exception as e:
                lg.logmessage(f'[ERRO] : Não foi possível coletar de {cliente} -> {e}')

        if not linhas:
            lg.logmessage('[AVISO] : Nenhuma linha de dados foi gerada. Finalizando script.')
            return None

        df = pd.DataFrame(linhas)
        
        # --- INÍCIO DA CORREÇÃO ---
        # Converte para datetime e REMOVE a informação de timezone antes de qualquer outra operação
        df['data_coleta'] = pd.to_datetime(df['data_coleta']).dt.tz_localize(None)
        # --- FIM DA CORREÇÃO ---

        df['data_coleta'] = df['data_coleta'].dt.floor("h")
        df['id_tab'] = df['data_coleta'].astype(str).str.replace('-', '', regex=False).str.replace(':','').str.replace(' ','') + df['instance_id']

        df = df.where(pd.notnull(df), None)

        df = df.groupby(['id_tab', 'instance_id','nome_chave','grupo','nome_instancia', 'cliente', 'vm_size', 'data_coleta'],as_index=False).agg(
            cpu_percent_use   =('cpu_percent_use','max'),
            memoria_use       =('memoria_use','max'),
            disk_free         =('disk_free','max'),
            memoria_disp      =('memoria_disp','max')
        )
        sha = SharePoint()
        try:
            sha.exportar_csv_com_data(df,f"coleta_aws_vm",data_file,"Documents/etl_capacity/diorama/aws")
            lg.logmessage(F'[ARQUIVO] : SALVO COM SUCESSO Documents/etl_capacity/diorama/aws/coleta_aws_vm{data_file}')
        
        except:
            lg.logmessage(F'[ARQUIVO] : NÃO FOI POSSIVEL SALVAR Documents/etl_capacity/diorama/aws/coleta_aws_vm{data_file}')

        return df

    def __init__(self):
        
        self.coleta_vm()

if __name__ == '__main__':
    ColetaAWS()

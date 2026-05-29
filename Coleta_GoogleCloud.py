# pyinstaller --onefile --noconsole Coleta_GoogleCloud.py
# https://cloud.google.com/monitoring/api/metrics_gcp_c?hl=pt-br

import warnings
warnings.filterwarnings('ignore')

from models.app import App
from models.configuracoes import Config
from models.logger import Log
from models.sharepoint import SharePoint

from google.cloud import monitoring_v3
from google.cloud import compute_v1
from google.oauth2 import service_account
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# ========= Inicializações =========
st = datetime.now()
data_file = st.strftime("%Y-%m-%d_%H_00_00")
data_ref = st.strftime("%Y-%m-%d")

lg = Log()
cfg = Config()
app = App()

class ColetaGoogle:

    def coleta_vm(self):


        # ========= Conexão =========
        lg.logmessage('[INICIO] : REALIZANDO COLETA GOOGLE CLOUD')

        caminho_json = f"arquivos/{i}.json"
        credentials = service_account.Credentials.from_service_account_file(caminho_json)
        project_id = credentials.project_id

        monitoring_client = monitoring_v3.MetricServiceClient(credentials=credentials)
        compute_client = compute_v1.InstancesClient(credentials=credentials)

        # ========= Intervalo de tempo =========
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=1)

        interval = monitoring_v3.TimeInterval(
            {
                "end_time": {"seconds": int(end_time.timestamp())},
                "start_time": {"seconds": int(start_time.timestamp())},
            }
        )

        # ========= Agregação =========
        aggregation = monitoring_v3.Aggregation(
            alignment_period={"seconds": 3600},
            per_series_aligner=monitoring_v3.Aggregation.Aligner.ALIGN_MEAN
        )

        # ========= Lista de todas as métricas =========
        metric_descriptors = monitoring_client.list_metric_descriptors(
            name=f"projects/{project_id}"
        )

        # ========= Dicionário para consolidar =========
        data_dict = {}
        nome_instancias_cache = {}

        for descriptor in metric_descriptors:
            metric_path = descriptor.type

            # 🔎 FILTRO: só métricas de VMs (resource.type="gce_instance")
            if "compute.googleapis.com/instance/" not in metric_path:
                continue

            metric_name = metric_path.replace(".", "_").replace("/", "_")

            try:
                results = monitoring_client.list_time_series(
                    request={
                        "name": f"projects/{project_id}",
                        "filter": f'metric.type="{metric_path}" AND resource.type="gce_instance"',
                        "interval": interval,
                        "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                        "aggregation": aggregation
                    }
                )

                for result in results:
                    resource = result.resource.labels
                    instance_id = resource.get("instance_id")
                    zone_path = resource.get("zone")  # ex: "us-central1-a"

                    # ========== CAPTURA NOME DA INSTÂNCIA ==========
                    instance_name = resource.get("instance_name")

                    # Se não tiver nome, consulta no Compute Engine
                    if not instance_name and instance_id:
                        cache_key = f"{zone_path}-{instance_id}"
                        if cache_key in nome_instancias_cache:
                            instance_name = nome_instancias_cache[cache_key]
                        else:
                            try:
                                zone_name = zone_path.split("/")[-1] if "/" in zone_path else zone_path
                                instance = compute_client.get(
                                    project=project_id,
                                    zone=zone_name,
                                    instance=instance_id
                                )
                                instance_name = instance.name
                                nome_instancias_cache[cache_key] = instance_name
                            except Exception:
                                instance_name = None

                    resource_type = result.resource.type

                    for point in result.points:
                        timestamp = point.interval.end_time
                        key = (instance_id, zone_path, timestamp)

                        if key not in data_dict:
                            data_dict[key] = {
                                "instance_id": instance_id,
                                "instance_name": instance_name,
                                "zone": zone_path,
                                "project_id": project_id,
                                "timestamp": timestamp,
                                "resource_type": resource_type,
                            }

                        value = None
                        if point.value.double_value:
                            value = point.value.double_value
                        elif point.value.int64_value:
                            value = point.value.int64_value
                        elif point.value.string_value:
                            value = point.value.string_value

                        data_dict[key][metric_name] = value

            except Exception as e:
                print(f"[ERRO] : Não consegui coletar {metric_path}: {e}")

        # ========= Converte para DataFrame =========
        df = pd.DataFrame(data_dict.values())
        lg.logmessage('[METRICAS] : SELECIONANDO MÉTRICAS A SEREM APRESENTADAS')

        # 🔹 Seleção das métricas principais
        colunas_existentes = [c for c in [
            'instance_id', 'instance_name', 'zone', 'project_id', 'timestamp', 'resource_type',
            'compute_googleapis_com_instance_cpu_utilization',
            'compute_googleapis_com_instance_disk_provisioning_size',
            'compute_googleapis_com_instance_memory_balloon_ram_size',
            'compute_googleapis_com_instance_memory_balloon_ram_used',
        ] if c in df.columns]

        df = df[colunas_existentes]

        lg.logmessage('[METRICAS] : REALIZANDO CÁLCULOS')

        if 'compute_googleapis_com_instance_cpu_utilization' in df.columns:
            df['compute_googleapis_com_instance_cpu_utilization'] = (df['compute_googleapis_com_instance_cpu_utilization'] * 100).round(2)

        if 'compute_googleapis_com_instance_disk_provisioning_size' in df.columns:
            df['compute_googleapis_com_instance_disk_provisioning_size'] = (df['compute_googleapis_com_instance_disk_provisioning_size'] / (1024 ** 3)).round(2)

        if 'compute_googleapis_com_instance_memory_balloon_ram_size' in df.columns:
            df['compute_googleapis_com_instance_memory_balloon_ram_size'] = np.ceil(df['compute_googleapis_com_instance_memory_balloon_ram_size'] / (1024 ** 3))

        if 'compute_googleapis_com_instance_memory_balloon_ram_used' in df.columns:
            df['compute_googleapis_com_instance_memory_balloon_ram_used'] = (df['compute_googleapis_com_instance_memory_balloon_ram_used'] / (1024 ** 3)).round(2)

        lg.logmessage('[METRICAS] : RENOMEANDO MÉTRICAS')
        
        try:
            df = df.rename(columns={
                "compute_googleapis_com_instance_disk_provisioning_size": "disk_disp",
                "compute_googleapis_com_instance_memory_balloon_ram_size": "memoria_disp",
                "compute_googleapis_com_instance_memory_balloon_ram_used": "memoria_use",
                "compute_googleapis_com_instance_cpu_utilization": "cpu_percent_use",
                'timestamp': 'data_coleta'
            })
        except: lg.logmessage('[ERRO] : Dataframe vazio')

        df["data_coleta"] = pd.to_datetime(df["data_coleta"]).dt.tz_localize(None).dt.floor("h")
        df['id_tab'] = (
            df['data_coleta'].astype(str).str.replace('-', '', regex=False)
            .str.replace(':', '').str.replace(' ', '') + df['instance_id']
        )

        # ========= Exporta =========
        #output_path = f"outputs/coleta_gcp_vm_{data_file}.xlsx"
        #df.to_excel(output_path, index=False)
        #lg.logmessage(f'[ARQUIVO] : ARQUIVO DE EXPORTAÇÃO SALVO EM {output_path}')
        
        sha = SharePoint()
        try:
            sha.exportar_csv_com_data(df,f"coleta_gcp_vm{i}",data_file,"Documents/etl_capacity/diorama/google")
            lg.logmessage(F'[ARQUIVO] : SALVO COM SUCESSO Documents/etl_capacity/diorama/google/coleta_gcp_vm{data_file}')
        
        except:
            lg.logmessage(F'[ARQUIVO] : NÃO FOI POSSIVEL SALVAR Documents/etl_capacity/diorama/google/coleta_gcp_vm{data_file}')

    def __init__(self):
        
        cfg.retry_com_proxy(self.coleta_vm)

def executar():
    lista = ['detran-dsis-dev-d54885821f32','saa-gedave-dev-eafd05cc2d10','saa-gedave-prod-8a677d1d80c6','sggd-diariasspmap-prod-9892a0f2d81f','detraninfosiga-prod-79f134d53db7','detran-repl-dad-mainf-c1d77c58958b']
    for projeto in lista:
        global i
        i = projeto
        try:
            ColetaGoogle()
        except:
            lg.logmessage(f'[ERRO] : {i}')

if __name__ == "__main__":
    executar()
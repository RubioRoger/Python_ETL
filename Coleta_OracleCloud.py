# https://cloud.oracle.com/block-storage/volumes?region=sa-saopaulo-1
# pyinstaller --onefile --noconsole Coleta_OracleCloud.py

import oci
import pandas as pd
from datetime import datetime, timedelta

import keys                        # arquivo de controle de chaves de acesso a OCI
from models.app import App
from models.configuracoes import Config
from models.logger import Log
from models.sharepoint import SharePoint


cfg                  = Config()                             # instanciando classe Config do arquivo auxiliar (__init__ "Prepara todo o ambiente")
lg                   = Log()                                # instanciando classe Log do arquivo auxiliar (configuta o arquivo de log)
app                  = App()                                # instanciando classe database do arquivo auxiliar (__init__ "Busca o arquivo config de acordo com o ambiente")

st                   = datetime.now()                       # data do momento da execução do processo
data_file            = st.strftime("%Y-%m-%d_%H_00_00")     # formato de data utilizado para o salvar o arquivo
tenancty             = ['prodespexadr']                     # lista de tenancity que será utilizada
DAYS_BACK            = 5                                    # quantidade de dias a serem processados
METRIC_RESOLUTION    = "1h"                                 # intervalo de tempo da coleta
end_time             = datetime.utcnow()
start_time           = end_time - timedelta(days=DAYS_BACK)

class coletaOci:

    def __init__(self):

        self.METRICS              = ["CpuUtilization", "MemoryUtilization"]
        cfg.retry_com_proxy(self.virtual_machine)

    def virtual_machine(self):
        for tenancy_name in tenancty:
            dicionario = getattr(keys, tenancy_name, None)
            if not dicionario:
                lg.logmessage(f"Dicionário {tenancy_name} não encontrado.")
                continue
        
            user_ocid           = dicionario['user_ocid']
            tenancy_ocid        = dicionario['tenancy_ocid']
            region_id           = dicionario['region_id']
            fingerprint         = dicionario['fingerprint']
            private_key_content = dicionario['private_key_content']
        
            config = {
                "user": user_ocid,
                "tenancy": tenancy_ocid,
                "region": region_id,
                "fingerprint": fingerprint,
                "key_content": private_key_content,
                "key_file": None
            }
        
            try:
                identity_client = oci.identity.IdentityClient(config)
                compute_client = oci.core.ComputeClient(config)
                monitoring_client = oci.monitoring.MonitoringClient(config)
        
                lg.logmessage(f"🔍 Buscando compartimentos para {tenancy_name}...")
                all_compartments = oci.pagination.list_call_get_all_results(
                    identity_client.list_compartments,
                    tenancy_ocid,
                    compartment_id_in_subtree=True,
                    access_level="ANY"
                ).data
                compartments_to_search = all_compartments + [oci.identity.models.Compartment(id=tenancy_ocid, name="Root")]
        
                lg.logmessage("🔍 Buscando VMs em estado RUNNING...")
                all_vms = []
                for compartment in compartments_to_search:
                    vms = oci.pagination.list_call_get_all_results(
                        compute_client.list_instances,
                        compartment.id,
                        lifecycle_state="RUNNING"
                    ).data
                    all_vms.extend(vms)
        
                if not all_vms:
                    lg.logmessage("⚠️ Nenhuma VM 'RUNNING' encontrada.")
                    continue
        
                lg.logmessage(f"✅ {len(all_vms)} VMs encontradas. Coletando métricas dos últimos {DAYS_BACK} dias...")
        
                results_list = []
        
                for vm in all_vms:
                    lg.logmessage(f"📡 VM: {vm.display_name} ({vm.id})")
        
                    metric_data_by_timestamp = {}
        
                    for metric in self.METRICS:
                        try:
                            query = f'{metric}[{METRIC_RESOLUTION}]{{resourceId = "{vm.id}"}}.mean()'
        
                            metric_details = oci.monitoring.models.SummarizeMetricsDataDetails(
                                namespace="oci_computeagent",
                                query=query,
                                start_time=start_time,
                                end_time=end_time,
                                resolution=METRIC_RESOLUTION
                            )
        
                            response = monitoring_client.summarize_metrics_data(
                                compartment_id=vm.compartment_id,
                                summarize_metrics_data_details=metric_details
                            ).data
        
                            if response:
                                for dp in response[0].aggregated_datapoints:
                                    ts = dp.timestamp.strftime("%Y-%m-%d %H:00:00")
                                    if ts not in metric_data_by_timestamp:
                                        metric_data_by_timestamp[ts] = {
                                            "data_coleta": ts,
                                            "time_created": vm.time_created.strftime("%Y-%m-%d %H:%M:%S"),
                                            #"tenancy": tenancy_ocid.split('.')[-1],
                                            "tenancy": tenancy_name,
                                            "compartment": next((c.name for c in compartments_to_search if c.id == vm.compartment_id), "N/A"),
                                            "instance_name": vm.display_name,
                                            "instance_region": vm.region,
                                            "instance_shape": vm.shape,
                                            "vcpus": vm.shape_config.ocpus,
                                            "memory_gb": vm.shape_config.memory_in_gbs
                                        }
                                    metric_data_by_timestamp[ts][metric] = dp.value
                        except Exception as e:
                            lg.logmessage(f"❌ Erro ao coletar {metric} da VM {vm.display_name}: {e}")
        
                    # Adiciona os dados coletados por timestamp
                    for row in metric_data_by_timestamp.values():
                        results_list.append(row)
        
                if results_list:
                    df = pd.DataFrame(results_list)
        
                    df.rename(columns={
                            'CpuUtilization': 'per_cpu',
                            'vcpus': 'cpu_disp',
                            'memory_gb': 'memoria_disp',
                            'MemoryUtilization': 'per_memoria'
                            
                            }, inplace=True)
                    sha                  = SharePoint()
                    try:
                        sha.exportar_csv_com_data(df,f"coleta_oracle_vm",data_file,"Documents/etl_capacity/diorama/oracle")
                        lg.logmessage(F'[ARQUIVO] : SALVO COM SUCESSO Documents/etl_capacity/diorama/oracle/coleta_oracle_vm{data_file}')
                    
                    except:
                        lg.logmessage(F'[ARQUIVO] : NÃO FOI POSSIVEL SALVAR Documents/etl_capacity/diorama/oracle/coleta_oracle_vm{data_file}')

                    return df
                else:
                    lg.logmessage("⚠️ Nenhuma métrica coletada para as VMs.")
        
            except Exception as e:
                lg.logmessage(f"❌ Erro geral ao processar tenancy {tenancy_name}: {e}")

if __name__ == '__main__':
    coletaOci()

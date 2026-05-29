private_key_content = """MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCJFWjcjPq3UTNRdaD0XptvgG7gizz71zBsVZeIbKuS21IIv9ZsdXzia+PvXXqsQS8EDpnyy07phifXYEL7LjywekQWZ0VkSn5C29mdUnBFYW7Lv14220TG37e31RHCg4aN46PkavFBenNdRHl6Ssu5gLLdZoTvpyg9RCgoC3lwDIoavklcOp2qlTl60FIMGyPh4OE3Ifl/qsTIZBxL0XKgHqnCyIcc1YYnVKfxy7IKa+qT1bHjFAXzIAB+UMiey8+FVbidZhQnjdvNlyfR1wNZTwoXYG5iEI78lo1awYwSt/nvbwVy1A5PeUvBC6WMjqPY3YHaWxEe8DRXngS6WoeNAgMBAAECggEADjBkn7uJ8fKaNLrPs6udPB/Xmi9fWxPtg7EiU7En2zYPWi99ItHQYOFZAPw0h+LhWnKmda6cluhXdGAW3sfs6TlmlckPsi9RvVrjPfj7/Pp2TOmcd2IfztP2QLVxtqgFg+dFng2BtkzV5xgA2OsoBiXvnaIQbXvoWtsUqvxxD+tdj7uUkg68cVFOTu0aLZylP20q1HHwv2j/rpF+tDLGYSEWnrxRXFt95kkZwQ9E6irgwVbASR2blUYmqLOJsQeoO8F6w/BgDj/Tq5kayFUCQjzQr8kyp42hn3FaIUIOv1VyVIGuOS+W9TBDHdyWNhYrVZCUfQgVRkPh0S56PDyOowKBgQC/mVSvxS+MeZOcaeoNIYsGZCU4LrndhFLzokuv83btRxWF53ueHA8ZA6JiPveQNvTcqk+YCz++M+Ohte/6bSwqmpTn1dsCv9lD85y0Dy+l5B2RegHn4pBwQVwfFiqnC1PYHq6vB4HrJMSLPiJq8O4jjPbA/861efsDG1qK17m2hwKBgQC3KSfFuFrYu39pF1ZZV/lRIj0ramKERzUOZWUxM48p0P05X9JtAZK7y47L5B1KGHWHYnnUyVKfJ3YJkxCdagLGDgfgaAV+B/K2x/d022/ix3EZ8YyzapnyC8hExShqIxpT+MqmgXFXf/MHMO9gqSkn3bUzVGJ+ihnQhxtmnJMCSwKBgH59OZ147nUs5jiC69OTa3bisneu0WHes+zIHnOgpcjr/teSBNhS6dy3u4Jk04dP4MO1ZCqacpCdLRBbTnzjih7uQpPzaU0dXtAviiqNRAWe3a5m/88Ykgap/6k+NxZksguh5e0DZc/ZTDAo6wvy1yR9MYIk31CLoR1h95pl5OMNAoGAY5dyM9VJOH3DCq6Q2iW2wAIBBsFi7hAV7kz91+H0H0Wu2uqabYEkew51B7Jypp5kEYhfPG93iGiZix03NJC3D2ADsmZ9TgkeVXqnuBe1X7cYbYXk/o2hRXZYn+QgVI3fu/cUobLSoURGLgvSrVltsmqgI1fn8mw/Gx7LrGDIor8CgYEAlxJFim6jL+oc/aAqS1QrEE8JNZDzCQaU/zv0cPemplJg7L0MTwBqAryyJGQxNnQ+tmkrKFpvWU4MdirwCiU5hWO6Mhw9BXdwfQTvb+6PZBMu2WmZhS1PUODcecolPzQe8EP1+FLREptfygb+n1UIZGHGaQwz7malE+lcVjuCLJE="""

import oci
import pandas as pd
from datetime import datetime, timedelta

from models.app        import App
from models.configuracoes import Config
from models.logger     import Log
from models.sharepoint import SharePoint

sha = SharePoint()
cfg = Config()
lg  = Log()
app = App()

# Agora retorna lista — uma entrada por tenancy
keys_list = app.key_oci()

st                = datetime.now()
data_file         = st.strftime("%Y-%m-%d_%H_00_00")
DAYS_BACK         = 5
METRIC_RESOLUTION = "1h"
end_time          = datetime.utcnow()
start_time        = end_time - timedelta(days=DAYS_BACK)


class coletaOci:

    def __init__(self):
        self.METRICS = ["CpuUtilization", "MemoryUtilization"]
        for keys in keys_list:
            try:
                self.virtual_machine(keys)
            except Exception as e:
                lg.logmessage(f"❌ Erro ao processar tenancy {keys.get('name')}: {e}")

    def virtual_machine(self, keys):

        user_ocid           = keys["user_ocid"]
        tenancy_ocid        = keys["tenancy_ocid"]
        region_id           = keys["region"]
        fingerprint         = keys["fingerprint"]
        tenancy_name        = keys["name"]

        lg.logmessage(f"Conectando tenancy OCI: {tenancy_name}")

        config = {
            "user":        user_ocid,
            "tenancy":     tenancy_ocid,
            "region":      region_id,
            "fingerprint": fingerprint,
            "key_content": private_key_content,
            "key_file":    None
        }

        try:
            identity_client   = oci.identity.IdentityClient(config)
            compute_client    = oci.core.ComputeClient(config)
            monitoring_client = oci.monitoring.MonitoringClient(config)

            lg.logmessage(f"🔍 Buscando compartimentos para {tenancy_name}...")

            all_compartments = oci.pagination.list_call_get_all_results(
                identity_client.list_compartments,
                tenancy_ocid,
                compartment_id_in_subtree=True,
                access_level="ANY"
            ).data

            compartments_to_search = all_compartments + [
                oci.identity.models.Compartment(id=tenancy_ocid, name="Root")
            ]

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
                lg.logmessage(f"⚠️ Nenhuma VM RUNNING em {tenancy_name}.")
                return pd.DataFrame()

            lg.logmessage(f"✅ {len(all_vms)} VMs em {tenancy_name}. Coletando métricas...")

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
                                        "data_coleta":     ts,
                                        "time_created":    vm.time_created.strftime("%Y-%m-%d %H:%M:%S"),
                                        "tenancy":         tenancy_name,
                                        "compartment":     next(
                                            (c.name for c in compartments_to_search if c.id == vm.compartment_id),
                                            "N/A"
                                        ),
                                        "instance_name":   vm.display_name,
                                        "instance_region": vm.region,
                                        "instance_shape":  vm.shape,
                                        "vcpus":           vm.shape_config.ocpus,
                                        "memory_gb":       vm.shape_config.memory_in_gbs
                                    }
                                metric_data_by_timestamp[ts][metric] = dp.value

                    except Exception as e:
                        lg.logmessage(f"❌ Erro ao coletar {metric} da VM {vm.display_name}: {e}")

                for row in metric_data_by_timestamp.values():
                    results_list.append(row)

            if not results_list:
                lg.logmessage(f"⚠️ Nenhuma métrica coletada para {tenancy_name}.")
                return pd.DataFrame()

            df = pd.DataFrame(results_list)
            df.rename(columns={
                "CpuUtilization":   "per_cpu",
                "vcpus":            "cpu_disp",
                "memory_gb":        "memoria_disp",
                "MemoryUtilization":"per_memoria"
            }, inplace=True)

            try:
                sha.exportar_csv(
                    df,
                    f"coleta_oracle_vm_{tenancy_name}",  # nome único por tenancy
                    data_file,
                    "Documents/etl_capacity/diorama/oracle"
                )
                lg.logmessage(f"[ARQUIVO] : SALVO — oracle/coleta_oracle_vm_{tenancy_name}_{data_file}")
            except Exception as e:
                lg.logmessage(f"[ARQUIVO] : NÃO FOI POSSIVEL SALVAR — {tenancy_name}: {e}")

            return df

        except Exception as e:
            lg.logmessage(f"❌ Erro geral ao processar {tenancy_name}: {e}")
            return pd.DataFrame()


if __name__ == '__main__':
    coletaOci()
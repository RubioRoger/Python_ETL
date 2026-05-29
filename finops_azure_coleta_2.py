from azure.identity import AzureCliCredential


from models.app             import App
from models.configuracoes   import Config
from models.database        import DataBase
from models.logger          import Log
from models.orquestrador    import etapa, projeto


import pandas as pd
import numpy  as np
import requests

from datetime import datetime, timedelta


app = App()
cfg = Config()
dbo = DataBase()
log = Log()

dbkey = app.key_db('fin')

@projeto(nome="Coleta Azure", descricao="Coleta métricas de billing da Azure")
class finops_azure():

    # =========================
    # 1 - LISTAR SUBSCRIPTIONS
    # =========================
    @etapa(nome='Lista de subscriptions')
    def listar_subscriptions(self):

        log.logmessage("[AZURE] Listando subscriptions...")

        credential = AzureCliCredential()

        token = credential.get_token(
            "https://management.azure.com/.default"
        ).token

        headers = {
            "Authorization": f"Bearer {token}"
        }

        url = (
            "https://management.azure.com/"
            "subscriptions?api-version=2019-11-01"
        )

        subs = []

        while url:

            response = requests.get(
                url,
                headers=headers
            )

            if response.status_code != 200:

                log.logmessage(
                    f"[ERRO SUBSCRIPTIONS] {response.text}"
                )

                return []

            data = response.json()

            for item in data.get("value", []):

                sub_id = item.get("subscriptionId")

                if sub_id:
                    subs.append(sub_id)

            url = data.get("nextLink")

        log.logmessage(
            f"[AZURE] {len(subs)} subscriptions encontradas"
        )

        return subs


    # =========================
    # 2 - PROCESSAR DADOS
    # =========================
    @etapa(nome='Coletar dados')
    def processar_dados(self, start_date, end_date):

        log.logmessage("[PROCESSAMENTO INICIADO]")

        credential = AzureCliCredential()

        token = credential.get_token(
            "https://management.azure.com/.default"
        ).token

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        enrollment = "6624533"

        url = (
            f"https://management.azure.com/providers/Microsoft.Billing/"
            f"billingAccounts/{enrollment}/providers/"
            f"Microsoft.Consumption/usageDetails"
            f"?api-version=2024-08-01"
            f"&$filter=properties/usageStart ge '{start_date}' "
            f"and properties/usageEnd lt '{end_date}'"
        )

        dados_total = []

        pagina = 1

        while url:

            log.logmessage(
                f"[BAIXANDO PAGINA] {pagina}"
            )

            response = requests.get(
                url,
                headers=headers,
                timeout=120
            )

            if response.status_code != 200:

                log.logmessage(
                    f"[ERRO API] {response.status_code}"
                )

                log.logmessage(response.text)

                raise Exception(
                    "Erro ao consultar billing API."
                )

            data = response.json()

            for item in data.get("value", []):

                props = item.get("properties", {})
                tags  = item.get("tags", {})

                linha = {

                    "id": item.get("id"),
                    "name": item.get("name"),
                    "type": item.get("type"),
                    "kind": item.get("kind"),

                    "enrollment": enrollment,

                    "billingAccountId": props.get("billingAccountId"),
                    "billingAccountName": props.get("billingAccountName"),

                    "billingProfileId": props.get("billingProfileId"),
                    "billingProfileName": props.get("billingProfileName"),

                    "billingPeriodStartDate": props.get("billingPeriodStartDate"),
                    "billingPeriodEndDate": props.get("billingPeriodEndDate"),

                    "date": props.get("date"),

                    "accountName": props.get("accountName"),
                    "accountOwnerId": props.get("accountOwnerId"),

                    "subscriptionId": props.get("subscriptionId"),
                    "subscriptionName": props.get("subscriptionName"),

                    "resourceGroup": props.get("resourceGroup"),
                    "resourceId": props.get("resourceId"),
                    "resourceName": props.get("resourceName"),
                    "resourceLocation": props.get("resourceLocation"),

                    "consumedService": props.get("consumedService"),
                    "product": props.get("product"),

                    "meterId": props.get("meterId"),
                    "meterName": props.get("meterName"),

                    "planName": props.get("planName"),

                    "chargeType": props.get("chargeType"),
                    "frequency": props.get("frequency"),
                    "pricingModel": props.get("pricingModel"),

                    "quantity": props.get("quantity"),

                    "unitPrice": props.get("unitPrice"),
                    "effectivePrice": props.get("effectivePrice"),
                    "payGPrice": props.get("payGPrice"),

                    "cost": props.get("cost"),

                    "billingCurrency": props.get("billingCurrency"),

                    "publisherName": props.get("publisherName"),
                    "publisherType": props.get("publisherType"),

                    "invoiceSection": props.get("invoiceSection"),

                    "isAzureCreditEligible": props.get("isAzureCreditEligible"),

                    "tags": tags
                }

                dados_total.append(linha)

            url = data.get("nextLink")

            pagina += 1

        log.logmessage("[GERANDO DATAFRAME]")

        df = pd.json_normalize(dados_total)

        if df.empty:

            log.logmessage("[SEM DADOS]")

            return pd.DataFrame()

        # =========================
        # NORMALIZAÇÃO
        # =========================

        df.columns = [
            col.replace(" ", "").replace("_", "")
            for col in df.columns
        ]

        df.columns = [
            cfg.cfg_config_header(col)
            for col in df.columns
        ]

        df = df.loc[:, ~df.columns.duplicated()]

        # =========================
        # TAGS
        # =========================

        colunas_tag = [
            col for col in df.columns
            if col.startswith('TAG')
        ]

        mapeamento_tags = {

            'TAGSAMBIENTE': 'AMBIENTE',
            'TAGSAMBEINTE': 'AMBIENTE',
            'TAGSAMBINTE': 'AMBIENTE',
            'TAGSAMBIETE': 'AMBIENTE',
            'TAGSENVIRONMENT': 'AMBIENTE',
            'TAGSXAMBIENTE': 'AMBIENTE',

            'TAGSPROJETO': 'PROJETO',
            'TAGSPROJECT': 'PROJETO',
            'TAGSXPROJETO': 'PROJETO',
            'TAGSNOMEDOPROJETO': 'PROJETO',
            'TAGSPOJETO': 'PROJETO',
            'TAGSSUBPROJETO': 'SUBPROJETO',

            'TAGSCRIADOR': 'CRIADOR',
            'TAGSCREATEDBY': 'CRIADOR',

            'TAGSSERVICO': 'SERVICO',

            'TAGSCLIENTE': 'CLIENTE',
            'TAGSNOMECLIENTE': 'CLIENTE',
            'TAGSXCLIENTE': 'CLIENTE',

            'TAGSDEPARTAMENTO': 'DEPARTAMENTO',

            'TAGSRESPONSAVEL': 'RESPONSAVEL',
            'TAGSSOLICITADOPOR': 'RESPONSAVEL',
            'TAGSAUTORIZADOPOR': 'RESPONSAVEL',
            'TAGSCRIADOPOR': 'RESPONSAVEL',
            'TAGSCREATOR': 'RESPONSAVEL',

            'TAGSGMU': 'GMUD',
            'TAGSGMUD': 'GMUD',

            'TAGSAPLICACAO': 'APLICACAO',
            'TAGSDESCRIPTION': 'DESCRICAO',
            'TAGSVALOR': 'VALOR'
        }

        colunas_finais = set(
            mapeamento_tags.values()
        )

        for col in colunas_finais:

            if col not in df.columns:
                df[col] = None

        tags_encontradas = set()

        for col in colunas_tag:

            tag_normalizada = mapeamento_tags.get(
                col,
                None
            )

            if tag_normalizada:

                df[tag_normalizada] = (
                    df[tag_normalizada]
                    .fillna(df[col])
                )

                tags_encontradas.add(col)

            else:

                log.logmessage(
                    f"[TAG IGNORADA] {col}"
                )

        for tag in mapeamento_tags.keys():

            if tag not in colunas_tag:

                log.logmessage(
                    f"[TAG NÃO ENCONTRADA] {tag}"
                )

        df = df.drop(
            columns=colunas_tag,
            errors='ignore'
        )

        log.logmessage(
            f"[FINALIZADO] {len(df)} registros"
        )

        return df


    # =========================
    # INIT
    # =========================

    def __init__(self):
    
        self.listar_subscriptions()
    
        # ─── CONFIGURAÇÃO DO PERÍODO ───────────────────────────────────────
        # Modo 1: Quantos dias atrás processar (relativo a hoje)
        DIAS_ATRAS = 7  # ex: processa os últimos 7 dias
    
        # Modo 2: Período fixo (defina as datas ou deixe None para usar Modo 1)
        DATA_INICIO_FIXA = '2026-05-17'  # None para usar DIAS_ATRAS
        DATA_FIM_FIXA    = '2026-05-28'  # None para usar DIAS_ATRAS
        # ───────────────────────────────────────────────────────────────────
    
        # Geração da lista de datas a processar
        if DATA_INICIO_FIXA and DATA_FIM_FIXA:
            data_inicio = datetime.strptime(DATA_INICIO_FIXA, '%Y-%m-%d')
            data_fim    = datetime.strptime(DATA_FIM_FIXA,    '%Y-%m-%d')
            log.logmessage(
                f"[MODO PERÍODO FIXO] "
                f"{DATA_INICIO_FIXA} ATÉ {DATA_FIM_FIXA}"
            )
        else:
            data_fim    = datetime.now() - timedelta(days=1)
            data_inicio = data_fim - timedelta(days=DIAS_ATRAS - 1)
            log.logmessage(
                f"[MODO RELATIVO] Últimos {DIAS_ATRAS} dias: "
                f"{data_inicio.strftime('%Y-%m-%d')} ATÉ "
                f"{data_fim.strftime('%Y-%m-%d')}"
            )
    
        # Monta lista de datas DIA A DIA dentro do intervalo
        total_dias = (data_fim - data_inicio).days + 1
        datas = [
            data_inicio + timedelta(days=i)
            for i in range(total_dias)
        ]
    
        # ─── LOOP DATA A DATA ──────────────────────────────────────────────
        for data_processar in datas:
    
            data_str     = data_processar.strftime('%Y-%m-%d')
            data_str_fim = (data_processar + timedelta(days=1)).strftime('%Y-%m-%d')
    
            log.logmessage(
                f"[PROCESSANDO DIA] "
                f"{data_str} ATÉ {data_str_fim}"
            )
    
            df_sem_tag = self.processar_dados(data_str, data_str_fim)
    
            if df_sem_tag.empty:
                log.logmessage(f"[SEM DADOS] {data_str}")
                continue
            
            data_minima = df_sem_tag['DATE'].min()
            df_sem_tag = df_sem_tag[df_sem_tag['DATE'] == data_minima]

            df2_sem_tag = df_sem_tag[['DATE']].drop_duplicates()
    
            dbo.conectar(dbkey)
    
            dbo.organizar_df(
                tabela='azure_billing_cost',
                df=df_sem_tag
            )
            dbo.validar_dados(
                tabela='azure_billing_cost',
                df=df_sem_tag
            )
            dbo.alinhar_colunas(
                tabela='azure_billing_cost',
                df=df_sem_tag
            )
    
            df_sem_tag = df_sem_tag.replace({np.nan: None})
            df_sem_tag = df_sem_tag.where(pd.notnull(df_sem_tag), None)
    
            dbo.deletar_informacoes(
                tabela='azure_billing_cost',
                df=df2_sem_tag
            )
            dbo.inserir_df(
                tabela='azure_billing_cost',
                df=df_sem_tag
            )
    
            dbo.desconectar()

if __name__ == '__main__':

    finops_azure()
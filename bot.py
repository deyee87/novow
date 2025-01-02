import discord
from discord.ext import commands, tasks
from discord import app_commands, Interaction, ButtonStyle, Activity, ActivityType
from discord.ui import View, Select, Button
from datetime import datetime
import itertools

# Removido a configuração do locale que não é compatível com o ambiente atual
# locale.setlocale(locale.LC_TIME, "pt_BR.utf8")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Variáveis globais
start_time = None
pause_time = None
total_time = 0
resultados_canal = None  # Canal de resultados configurado
usuario_iniciado = None  # Usuário que iniciou o ponto

# Lista de status dinâmicos
status_mensagens = itertools.cycle([
    "Harmony",
    "Turbinando carros com stage3",
    "Fazendo revisão na",
    "Feito por Felipe Otto"
])

class PontoView(View):
    """Classe para botões interativos do sistema de ponto."""

    def __init__(self):
        super().__init__()
        self.pausado = False

    @discord.ui.button(label="INICIAR PONTO", style=ButtonStyle.green)
    async def abrir_ponto(self, interaction: Interaction, button: Button):
        global start_time, usuario_iniciado
        if start_time:
            await interaction.response.send_message("❌ O ponto já está iniciado!", ephemeral=True)
        else:
            start_time = datetime.now()
            usuario_iniciado = interaction.user.mention
            await interaction.response.send_message(f"✅ Ponto iniciado por {usuario_iniciado} às {start_time.strftime('%H:%M:%S')}", ephemeral=True)

    @discord.ui.button(label="PAUSAR PONTO", style=ButtonStyle.blurple)
    async def pausar_ou_retornar_ponto(self, interaction: Interaction, button: Button):
        global start_time, pause_time, total_time

        if not start_time:
            await interaction.response.send_message("❌ O ponto ainda não foi iniciado!", ephemeral=True)
            return

        if self.pausado:
            # Retomar o ponto
            start_time = datetime.now()
            pause_time = None
            button.label = "PAUSAR PONTO"
            button.style = ButtonStyle.blurple
            self.pausado = False
            await interaction.message.edit(view=self)
            await interaction.response.send_message(f"▶️ Ponto retomado às {start_time.strftime('%H:%M:%S')}.", ephemeral=True)
        else:
            # Pausar o ponto
            pause_time = datetime.now()
            elapsed = (pause_time - start_time).total_seconds()
            total_time += elapsed
            button.label = "RETORNAR"
            button.style = ButtonStyle.green
            self.pausado = True
            await interaction.message.edit(view=self)
            await interaction.response.send_message(
                f"⏸️ Ponto pausado às {pause_time.strftime('%H:%M:%S')}. Tempo acumulado: {int(total_time // 60)} minutos.",
                ephemeral=True,
            )

    @discord.ui.button(label="FINALIZAR PONTO", style=ButtonStyle.red)
    async def finalizar_ponto(self, interaction: Interaction, button: Button):
        global start_time, pause_time, total_time, resultados_canal, usuario_iniciado

        if not start_time:
            await interaction.response.send_message("❌ O ponto ainda não foi iniciado!", ephemeral=True)
        else:
            end_time = datetime.now()
            if not pause_time:
                total_time += (end_time - start_time).total_seconds()
            hours, remainder = divmod(total_time, 3600)
            minutes, seconds = divmod(remainder, 60)

            embed = discord.Embed(
                title="⏱️ Resumo do Ponto Eletrônico",
                color=discord.Color.green()
            )
            embed.add_field(name="🔧 MECANICO", value=f"{usuario_iniciado}", inline=False)
            embed.add_field(name="🟢 Entrada", value=f"{start_time.strftime('%A, %d de %B de %Y %H:%M')}", inline=False)
            embed.add_field(name="🔴 Saída", value=f"{end_time.strftime('%A, %d de %B de %Y %H:%M')}", inline=False)
            embed.add_field(name="⌚ Tempo Total", value=f"{int(hours):02}h {int(minutes):02}m {int(seconds):02}s", inline=False)

            # Enviar resumo no canal de resultados
            if resultados_canal:
                await resultados_canal.send(embed=embed)
            else:
                await interaction.response.send_message("❌ Canal de resultados não configurado!", ephemeral=True)

            # Resetar variáveis
            start_time = None
            pause_time = None
            total_time = 0
            usuario_iniciado = None

            await interaction.response.send_message("✅ Ponto finalizado com sucesso!", ephemeral=True)

class ConfigPontoView(View):
    """Classe que define as interações de configuração com menus de seleção.""" 

    def __init__(self, canais):
        super().__init__()
        self.add_item(SelectCanal(canais, "Selecione o canal para enviar mensagens do ponto:", enviar_mensagem=True))
        self.add_item(SelectCanal(canais, "Selecione o canal para enviar os resultados:", resultados=True))

class SelectCanal(discord.ui.Select):
    """Menu suspenso para selecionar canais disponíveis."""

    def __init__(self, canais, placeholder, enviar_mensagem=False, resultados=False):
        self.enviar_mensagem = enviar_mensagem
        self.resultados = resultados
        options = [
            discord.SelectOption(label=canal.name, description=f"Selecionar o canal '{canal.name}'")
            for canal in canais
        ]
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        global resultados_canal

        canal_nome = self.values[0]
        canal = discord.utils.get(interaction.guild.text_channels, name=canal_nome)

        if self.enviar_mensagem:
            # Enviar a mensagem fixa do ponto no canal selecionado
            embed = discord.Embed(
                title="📌 Sistema de Ponto Eletrônico Harmony",
                description="Ao entrar em serviço, registre seu ponto eletrônico!",
                color=discord.Color.green()
            )
            view = PontoView()
            await canal.send(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Mensagem fixa enviada no canal {canal.mention}!", ephemeral=True)

        elif self.resultados:
            resultados_canal = canal
            await interaction.response.send_message(f"✅ Canal de resultados configurado: {canal.mention}!", ephemeral=True)

@bot.tree.command(name="configponto", description="Configurar o canal para o ponto eletrônico")
async def configponto(interaction: Interaction):
    """Comando para configurar os canais do ponto eletrônico."""
    canais = interaction.guild.text_channels
    if not canais:
        await interaction.response.send_message("❌ Nenhum canal de texto disponível!", ephemeral=True)
        return

    view = ConfigPontoView(canais)
    await interaction.response.send_message("📌 Configure os canais para o ponto eletrônico:", view=view, ephemeral=True)

@tasks.loop(seconds=30)
async def mudar_status():
    """Altera dinamicamente o status do bot."""
    nova_mensagem = next(status_mensagens)
    await bot.change_presence(activity=Activity(type=ActivityType.watching, name=nova_mensagem))

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Comandos sincronizados: {len(synced)}")
        print(f"Bot conectado como {bot.user}")
        mudar_status.start()  # Inicia a tarefa de alternar status
    except Exception as e:
        print(f"Erro ao sincronizar comandos: {e}")

# Substitua 'SEU_TOKEN_AQUI' pelo token do seu bot
bot.run("MTMyNDE0MzMyNTU2OTM1NTc5Nw.G7lDPo.1d1HQ47sKPQKD5qlVEZ7JcjqQgPoXpXAd5bVVc")

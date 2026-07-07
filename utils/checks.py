import discord


def is_admin(interaction: discord.Interaction):

    return interaction.user.guild_permissions.administrator
import discord


class Embeds:

    @staticmethod
    def success(title, description):

        return discord.Embed(
            title=title,
            description=description,
            color=discord.Color.green()
        )

    @staticmethod
    def error(title, description):

        return discord.Embed(
            title=title,
            description=description,
            color=discord.Color.red()
        )
class RoleService:

    @staticmethod
    def get_reaper_roles(guild):

        return sorted(
            [
                role
                for role in guild.roles
                if role.name.endswith("Reaper")
            ],
            key=lambda r: r.position,
            reverse=True
        )
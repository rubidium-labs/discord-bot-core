"""The core's own translations.

This catalog holds the strings the core itself prints: the ``/core`` cog's replies,
the error handler's user-facing messages and the UI kit's built-in text. Keys are
symbolic and mirrored at the call site with
:func:`discord.app_commands.locale_str`. Every key has an ``en-US`` and a ``fr``
entry; ``en-US`` is also the fallback used when no translator is available (tests,
or an interaction without one).
"""

from __future__ import annotations

from discord_bot_core.i18n.catalog import TranslationCatalog

CORE_CATALOG = TranslationCatalog()
"""The core's translations, keyed by symbolic message key."""

_MESSAGES: dict[str, dict[str, str]] = {
    "core.sync.done": {
        "en-US": "Commands synced",
        "fr": "Commandes synchronisées",
    },
    "core.group.description": {
        "en-US": "Core administration: command sync and extensions.",
        "fr": "Administration du cœur : synchronisation des commandes et extensions.",
    },
    "core.sync.group.description": {
        "en-US": "Publish the application commands.",
        "fr": "Publier les commandes d'application.",
    },
    "core.sync.global.description": {
        "en-US": "Publish the global commands.",
        "fr": "Publier les commandes globales.",
    },
    "core.sync.dev.description": {
        "en-US": "Sync the dev guild's commands.",
        "fr": "Synchroniser les commandes de la guilde de développement.",
    },
    "core.sync.guild.description": {
        "en-US": "Sync the commands of one guild.",
        "fr": "Synchroniser les commandes d'une guilde.",
    },
    "core.sync.guild.guild_id": {
        "en-US": "The guild id to sync to.",
        "fr": "L'identifiant de la guilde vers laquelle synchroniser.",
    },
    "core.sync.field.scope": {
        "en-US": "Scope",
        "fr": "Portée",
    },
    "core.sync.field.count": {
        "en-US": "Count",
        "fr": "Nombre",
    },
    "core.sync.field.commands": {
        "en-US": "Commands",
        "fr": "Commandes",
    },
    "core.sync.scope.global": {
        "en-US": "global",
        "fr": "global",
    },
    "core.sync.scope.dev": {
        "en-US": "dev guild (reset, copy, sync)",
        "fr": "guilde de développement (réinitialiser, copier, synchroniser)",
    },
    "core.sync.scope.dev_prod": {
        "en-US": "dev guild (admin commands only)",
        "fr": "guilde de développement (commandes d'administration uniquement)",
    },
    "core.sync.scope.guild": {
        "en-US": "guild {guild_id}",
        "fr": "guilde {guild_id}",
    },
    "core.sync.devmode.field": {
        "en-US": "Note",
        "fr": "Note",
    },
    "core.sync.devmode.note": {
        "en-US": (
            "environment is dev; global commands are normally not published here."
        ),
        "fr": (
            "l'environnement est dev ; les commandes globales ne sont normalement "
            "pas publiées ici."
        ),
    },
    "core.ext.group.description": {
        "en-US": "Load, unload, reload and list the extensions.",
        "fr": "Charger, décharger, recharger et lister les extensions.",
    },
    "core.ext.load.description": {
        "en-US": "Load an extension.",
        "fr": "Charger une extension.",
    },
    "core.ext.load.name": {
        "en-US": "The extension to load.",
        "fr": "L'extension à charger.",
    },
    "core.ext.unload.description": {
        "en-US": "Unload an extension.",
        "fr": "Décharger une extension.",
    },
    "core.ext.unload.name": {
        "en-US": "The extension to unload.",
        "fr": "L'extension à décharger.",
    },
    "core.ext.reload.description": {
        "en-US": "Reload an extension.",
        "fr": "Recharger une extension.",
    },
    "core.ext.reload.name": {
        "en-US": "The extension to reload.",
        "fr": "L'extension à recharger.",
    },
    "core.ext.list.description": {
        "en-US": "List the extensions and their state.",
        "fr": "Lister les extensions et leur état.",
    },
    "core.ext.list.title": {
        "en-US": "Extensions",
        "fr": "Extensions",
    },
    "core.ext.list.loaded": {
        "en-US": "Loaded ({count})",
        "fr": "Chargées ({count})",
    },
    "core.ext.list.available": {
        "en-US": "Available ({count})",
        "fr": "Disponibles ({count})",
    },
    "core.ext.action.loaded": {
        "en-US": "Extension loaded",
        "fr": "Extension chargée",
    },
    "core.ext.action.unloaded": {
        "en-US": "Extension unloaded",
        "fr": "Extension déchargée",
    },
    "core.ext.action.reloaded": {
        "en-US": "Extension reloaded",
        "fr": "Extension rechargée",
    },
    "core.ext.field.extension": {
        "en-US": "Extension",
        "fr": "Extension",
    },
    "core.ext.field.next": {
        "en-US": "Next",
        "fr": "Ensuite",
    },
    "core.ext.next.hint": {
        "en-US": "Command definitions changed; run `/core sync dev`.",
        "fr": "Les définitions de commandes ont changé ; lancez `/core sync dev`.",
    },
    "core.ext.names.none": {
        "en-US": "none",
        "fr": "aucune",
    },
    "core.ext.error.no_manager": {
        "en-US": "No extensions package is configured.",
        "fr": "Aucun paquet d'extensions n'est configuré.",
    },
    "core.sync.guild.invalid": {
        "en-US": "`{guild_id}` is not a valid guild id.",
        "fr": "`{guild_id}` n'est pas un identifiant de guilde valide.",
    },
    "errors.generic": {
        "en-US": "Something went wrong. Error id: `{error_id}`.",
        "fr": "Une erreur est survenue. Identifiant d'erreur : `{error_id}`.",
    },
    "errors.out_of_date": {
        "en-US": "This command is out of date, try again in a few minutes.",
        "fr": "Cette commande est obsolète, réessayez dans quelques minutes.",
    },
    "errors.check_failure": {
        "en-US": "You can't use this command.",
        "fr": "Vous ne pouvez pas utiliser cette commande.",
    },
    "errors.no_private_message": {
        "en-US": "This command only works in a server.",
        "fr": "Cette commande ne fonctionne que dans un serveur.",
    },
    "errors.cooldown": {
        "en-US": "Try again in {seconds} s.",
        "fr": "Réessayez dans {seconds} s.",
    },
    "errors.transformer": {
        "en-US": "Invalid value for `{option}`.",
        "fr": "Valeur invalide pour `{option}`.",
    },
    "errors.permissions": {
        "en-US": "You need the {permissions} permission(s) to use this command.",
        "fr": "Vous avez besoin de la ou des permissions {permissions} pour utiliser "
        "cette commande.",
    },
    "ui.view.other_user": {
        "en-US": "This menu belongs to someone else.",
        "fr": "Ce menu appartient à quelqu'un d'autre.",
    },
}

for _key, _translations in _MESSAGES.items():
    CORE_CATALOG.register(_key, _translations)

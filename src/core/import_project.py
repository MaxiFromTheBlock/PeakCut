"""Import Slice 3 / Brocken B(ii): bestaetigte Rollen -> Laufzeit-Projekt.

Keine Namensheuristik mehr — die WAHRHEIT sind die vom Nutzer bestaetigten Rollen
(ConfirmedImportSlots). Carl-Adapter Opt. 2: das Laufzeit-PeakCutProject bekommt fuer den
legacy XMLExporter Mics + [Mix] in mic_tracks (der Markerstellen-XML-Audioblock baut
direkt von dort -> Pin-1), waehrend mix_track exakt die bestaetigte Mix-Rolle traegt.
Qt-frei, testbar.
"""
from .project import PeakCutProject


def build_project_from_confirmed_slots(slots):
    """ConfirmedImportSlots -> PeakCutProject (Laufzeit-Form). Adapter: legacy mic_tracks
    = echte Mics + [Mix] (Pin-1). mix_track = exakt slots.mix (auch None) — set_files
    wuerde sonst aus den Mics per Namen einen Mix "erkennen"; die bestaetigte Rolle ist
    aber die Wahrheit, darum ueberschreiben wir mix_track danach explizit."""
    legacy_mics = list(slots.mics) + ([slots.mix] if slots.mix else [])
    project = PeakCutProject()
    project.set_files(
        keyboard=slots.marker,
        mics=legacy_mics,
        videos=list(slots.videos),
        mix=slots.mix,
        transcript=slots.transcript,
    )
    # Rolle = Wahrheit: keine stille Namens-Mix-Erkennung aus den Mics.
    project.mix_track = slots.mix
    return project


__all__ = ["build_project_from_confirmed_slots"]

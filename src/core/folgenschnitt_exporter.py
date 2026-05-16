import os
from xml.sax.saxutils import escape

from utils import ms_to_frames, parse_timecode_to_ms

from .exporters import BaseExporter, _file_url, _probe_audio_info, _probe_video_info


class FolgenschnittXMLExporter(BaseExporter):
    """Export a flat FCP7 XML sequence from Folgenschnitt edit decisions."""

    def export(self, session) -> str:
        decisions = list(getattr(session, "folgenschnitt_edit_decisions", []) or [])
        if not decisions:
            return ""

        os.makedirs(session.project.export_dir, exist_ok=True)

        fps = session.config.get("fps", 25)
        total_duration_ms = max(d.end_ms for d in decisions)
        total_frames = ms_to_frames(total_duration_ms, fps)

        video_paths = list(session.project.videos)
        audio_paths = list(session.project.mic_tracks)

        offset_lookup_ms = {}
        for video_filename, offset_str in getattr(session, "video_offsets", []) or []:
            offset_lookup_ms[video_filename] = parse_timecode_to_ms(offset_str, fps)

        vid_w, vid_h = 3840, 2160
        if video_paths:
            vid_w, vid_h = _probe_video_info(video_paths[0])

        sample_rate, bit_depth, channels = 48000, 16, 2
        if audio_paths:
            sample_rate, bit_depth, channels = _probe_audio_info(audio_paths[0])

        gastname = session.project.guest_name
        xml_path = os.path.join(session.project.export_dir, f"Folgenschnitt - {gastname}.xml")

        rate_block = f"<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate>"
        tc_block = f"""<timecode>
        {rate_block}
        <string>00:00:00:00</string>
        <frame>0</frame>
        <displayformat>NDF</displayformat>
      </timecode>"""

        video_file_ids = {}
        audio_file_ids = {}

        with open(xml_path, "w") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<!DOCTYPE xmeml>\n')
            f.write('<xmeml version="5">\n')
            f.write('  <sequence id="folgenschnitt-sequence">\n')
            f.write(f'    <name>{escape("Folgenschnitt - " + gastname)}</name>\n')
            f.write(f'    <duration>{total_frames}</duration>\n')
            f.write(f'    {rate_block}\n')
            f.write(f'    {tc_block}\n')
            f.write('    <format>\n')
            f.write('      <samplecharacteristics>\n')
            f.write(f'        <width>{vid_w}</width>\n')
            f.write(f'        <height>{vid_h}</height>\n')
            f.write('        <pixelaspectratio>Square</pixelaspectratio>\n')
            f.write(f'        {rate_block}\n')
            f.write('      </samplecharacteristics>\n')
            f.write('    </format>\n')
            f.write('    <media>\n')

            f.write('      <video>\n')
            f.write('        <format>\n')
            f.write('          <samplecharacteristics>\n')
            f.write(f'            <width>{vid_w}</width>\n')
            f.write(f'            <height>{vid_h}</height>\n')
            f.write('            <pixelaspectratio>Square</pixelaspectratio>\n')
            f.write(f'            {rate_block}\n')
            f.write('          </samplecharacteristics>\n')
            f.write('        </format>\n')
            f.write('        <track>\n')

            for idx, decision in enumerate(decisions):
                video_path = decision.camera_path
                video_file = os.path.basename(video_path)
                video_name = os.path.splitext(video_file)[0]
                offset_ms = offset_lookup_ms.get(video_file, 0)

                file_id = video_file_ids.get(video_path)
                is_first_file_ref = file_id is None
                if file_id is None:
                    file_id = f"file-folgenschnitt-video-{len(video_file_ids) + 1}"
                    video_file_ids[video_path] = file_id

                rec_start_f = ms_to_frames(decision.start_ms, fps)
                rec_end_f = ms_to_frames(decision.end_ms, fps)
                clip_dur_f = rec_end_f - rec_start_f

                source_in_ms = max(0, decision.start_ms + offset_ms)
                source_in_f = ms_to_frames(source_in_ms, fps)
                source_out_f = source_in_f + clip_dur_f

                f.write(f'          <clipitem id="clipitem-folgenschnitt-v{idx + 1}">\n')
                f.write(f'            <name>{escape(video_name)}</name>\n')
                f.write(f'            <duration>{clip_dur_f}</duration>\n')
                f.write(f'            {rate_block}\n')
                f.write(f'            <start>{rec_start_f}</start>\n')
                f.write(f'            <end>{rec_end_f}</end>\n')
                f.write(f'            <in>{source_in_f}</in>\n')
                f.write(f'            <out>{source_out_f}</out>\n')

                if is_first_file_ref:
                    f.write(f'            <file id="{file_id}">\n')
                    f.write(f'              <name>{escape(video_file)}</name>\n')
                    f.write(f'              <pathurl>{_file_url(video_path)}</pathurl>\n')
                    f.write(f'              {rate_block}\n')
                    f.write(f'              {tc_block}\n')
                    f.write('              <media>\n')
                    f.write('                <video>\n')
                    f.write('                  <samplecharacteristics>\n')
                    f.write(f'                    <width>{vid_w}</width>\n')
                    f.write(f'                    <height>{vid_h}</height>\n')
                    f.write('                    <pixelaspectratio>Square</pixelaspectratio>\n')
                    f.write(f'                    {rate_block}\n')
                    f.write('                  </samplecharacteristics>\n')
                    f.write('                </video>\n')
                    f.write('              </media>\n')
                    f.write('            </file>\n')
                else:
                    f.write(f'            <file id="{file_id}"/>\n')

                f.write('          </clipitem>\n')

            f.write('        </track>\n')
            f.write('      </video>\n')

            f.write('      <audio>\n')
            f.write('        <format>\n')
            f.write('          <samplecharacteristics>\n')
            f.write(f'            <samplerate>{sample_rate}</samplerate>\n')
            f.write(f'            <depth>{bit_depth}</depth>\n')
            f.write('          </samplecharacteristics>\n')
            f.write('        </format>\n')

            for track_idx, audio_path in enumerate(audio_paths):
                audio_file = os.path.basename(audio_path)
                audio_name = os.path.splitext(audio_file)[0]
                file_id = f"file-folgenschnitt-audio-{track_idx + 1}"
                audio_file_ids[audio_path] = file_id

                f.write('        <track>\n')
                f.write(f'          <clipitem id="clipitem-folgenschnitt-a{track_idx + 1}">\n')
                f.write(f'            <name>{escape(audio_name)}</name>\n')
                f.write(f'            <duration>{total_frames}</duration>\n')
                f.write(f'            {rate_block}\n')
                f.write('            <start>0</start>\n')
                f.write(f'            <end>{total_frames}</end>\n')
                f.write('            <in>0</in>\n')
                f.write(f'            <out>{total_frames}</out>\n')
                f.write(f'            <file id="{file_id}">\n')
                f.write(f'              <name>{escape(audio_file)}</name>\n')
                f.write(f'              <pathurl>{_file_url(audio_path)}</pathurl>\n')
                f.write(f'              {rate_block}\n')
                f.write(f'              {tc_block}\n')
                f.write('              <media>\n')
                f.write('                <audio>\n')
                f.write('                  <samplecharacteristics>\n')
                f.write(f'                    <samplerate>{sample_rate}</samplerate>\n')
                f.write(f'                    <depth>{bit_depth}</depth>\n')
                f.write('                  </samplecharacteristics>\n')
                f.write(f'                  <channelcount>{channels}</channelcount>\n')
                f.write('                </audio>\n')
                f.write('              </media>\n')
                f.write('            </file>\n')
                f.write('            <sourcetrack>\n')
                f.write('              <mediatype>audio</mediatype>\n')
                f.write('            </sourcetrack>\n')
                f.write('          </clipitem>\n')
                f.write('        </track>\n')

            f.write('      </audio>\n')
            f.write('    </media>\n')
            f.write('  </sequence>\n')
            f.write('</xmeml>\n')

        session.status_update.emit(f"Folgenschnitt XML exported: {os.path.basename(xml_path)}")
        return xml_path

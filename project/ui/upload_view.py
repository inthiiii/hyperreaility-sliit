"""Sidebar panel: add an incident from JSON (NOC Coordinator, Administrator)."""
import streamlit as st

from project.auth import PermissionDenied, can
from project.ui.upload_service import UploadRejected, remove_upload, save_upload


def _add(root, existing, user):
    file = st.session_state.get('upload_file')
    if file is None:
        st.session_state['upload_feedback'] = (False, 'Choose a JSON file first.')
        return
    try:
        key = save_upload(root, file.getvalue(), existing, user)
        st.session_state['pending_scenario'] = key
        st.session_state['upload_feedback'] = (True, f'Added and selected {key.rsplit("/", 1)[-1][:-5]}.')
    except (UploadRejected, PermissionDenied) as error:
        st.session_state['upload_feedback'] = (False, str(error))


def _remove(root, key, user):
    try:
        remove_upload(root, key, user)
        st.session_state['upload_feedback'] = (True, 'Uploaded incident removed.')
    except (UploadRejected, PermissionDenied) as error:
        st.session_state['upload_feedback'] = (False, str(error))


def render_upload(root, catalog, choice, user):
    if not can(user, 'upload_scenario'):
        return
    with st.expander('＋ Add an incident (JSON)'):
        st.caption('Visible incident input only (sites, links, roads, crews, generators, services, reports). '
                   'Checked against the same contract as the dataset. Uploaded incidents can be planned and '
                   'approved, but have no simulator answer.')
        if choice is not None:
            st.download_button('Download the current incident as a template', choice.scenario.model_dump_json(indent=2),
                               file_name=f'{choice.scenario.scenario_id}.json', mime='application/json',
                               key='upload_template', on_click='ignore')
        st.file_uploader('Incident JSON', type=['json'], key='upload_file')
        existing = [item.scenario.scenario_id for item in catalog.choices]
        st.button('Add incident', key='upload_add', on_click=_add, args=(root, existing, user), width='stretch')
        feedback = st.session_state.pop('upload_feedback', None)
        if feedback:
            (st.success if feedback[0] else st.error)(feedback[1])
        if choice is not None and choice.key.startswith('.relink/uploads/'):
            st.button('Remove this uploaded incident', key='upload_remove', on_click=_remove,
                      args=(root, choice.key, user), width='stretch')

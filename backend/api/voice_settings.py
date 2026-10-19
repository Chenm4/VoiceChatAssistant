from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.user_workspace import user_config, user_state, workspace, write_json

router = APIRouter(prefix='/voice-settings', tags=['语音配置'])


class VoiceSettings(BaseModel):
    provider: Literal['soniox', 'volcengine'] = 'soniox'
    soniox_api_key: str = Field(default='', max_length=4096)
    volcengine_app_id: str = Field(default='', max_length=256)
    volcengine_token: str = Field(default='', max_length=4096)
    doubao_app_id: str = Field(default='', max_length=256)
    doubao_access_token: str = Field(default='', max_length=4096)


@router.get('')
async def get_voice_settings():
    return VoiceSettings(
        provider=user_config('ASR_CONFIG').get('provider', 'soniox'),
        soniox_api_key=user_config('SONIOX_CONFIG').get('api_key', ''),
        volcengine_app_id=user_config('VOLCENGINE_CONFIG').get('appid', ''),
        volcengine_token=user_config('VOLCENGINE_CONFIG').get('token', ''),
        doubao_app_id=user_config('DOUBAO_REALTIME').get('app_id', ''),
        doubao_access_token=user_config('DOUBAO_REALTIME').get('access_token', ''),
    )


@router.post('')
async def save_voice_settings(values: VoiceSettings):
    if user_state().streaming_asr:
        raise HTTPException(409, '请先停止录音再修改语音配置')
    settings = workspace().settings
    settings['ASR_CONFIG']['provider'] = values.provider
    settings['SONIOX_CONFIG']['api_key'] = values.soniox_api_key.strip()
    settings['VOLCENGINE_CONFIG'].update(appid=values.volcengine_app_id.strip(), token=values.volcengine_token.strip())
    settings['DOUBAO_REALTIME'].update(app_id=values.doubao_app_id.strip(), access_token=values.doubao_access_token.strip())
    write_json(workspace().path('settings.json'), settings)
    user_state().streaming_asr_pool = None
    return {'success': True}

from notebooklm_cdp_cli.products.gemini.contract import probe_gemini_contract
from notebooklm_cdp_cli.products.gemini.ops import GeminiPage


def _dom_snapshot(*, buttons=None, inputs=None):
    buttons = buttons or []
    inputs = inputs or []
    return {
        "buttons": [
            {
                "selector": f'[data-notebooklm-cdp-gemini-probe="button-{index}"]',
                "tag": "BUTTON",
                **button,
            }
            for index, button in enumerate(buttons)
        ],
        "inputs": [
            {
                "selector": f'[data-notebooklm-cdp-gemini-probe="input-{index}"]',
                "tag": "DIV",
                **input_node,
            }
            for index, input_node in enumerate(inputs)
        ],
    }


def test_probe_detects_chinese_prompt_send_upload_and_image_entry():
    contract = probe_gemini_contract(
        _dom_snapshot(
            buttons=[{"aria": "发送"}, {"aria": "打开文件上传菜单"}, {"text": "制作图片"}],
            inputs=[{"tag": "TEXTAREA", "placeholder": "向 Gemini 提问"}],
        )
    )

    assert contract.prompt_input is not None
    assert contract.prompt_input.kind == "textarea"
    assert contract.send_button is not None
    assert contract.send_button.label == "发送"
    assert contract.upload_button is not None
    assert contract.image_entry is not None


def test_image_mode_latch_accepts_cancel_selection_label():
    page = GeminiPage.__new__(GeminiPage)
    contract = probe_gemini_contract(
        _dom_snapshot(
            buttons=[{"text": "取消选择 制作图片"}],
            inputs=[{"tag": "TEXTAREA", "placeholder": "描述要生成的图片"}],
        )
    )

    assert page._is_image_mode_latched(contract) is True

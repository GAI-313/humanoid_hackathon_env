"""Unitree R1 用の RPC クライアント（unitree_sdk2py の不足分を補う）。

pixi 環境に入る unitree_sdk2py には `unitree_sdk2py.r1` が含まれない
（上流リポジトリの r1/ に __init__.py が無く、パッケージ化から漏れるため）。
このファイルを scripts/ にコピーし、`from r1_clients import R1LocoClient` のように使う。

- R1LocoClient      : 上流 unitree_sdk2py/r1/loco/r1_loco_client.py と同等 + GetFsmId
- R1ArmActionClient : 公式 R1 マニュアル「arm_action_interface」の仕様に基づく実装
                      （G1ArmActionClient とはパラメータ形式・アクション ID 表が異なる）
"""
import json

from unitree_sdk2py.rpc.client import Client

# ---------------------------------------------------------------- loco (sport)
LOCO_SERVICE_NAME = "sport"  # ai_sport < 1.0.2.0 の古い機体では "loco"
LOCO_API_VERSION = "1.0.0.0"

ROBOT_API_ID_LOCO_GET_FSM_ID = 7001
ROBOT_API_ID_LOCO_SET_FSM_ID = 7101
ROBOT_API_ID_LOCO_SET_VELOCITY = 7105
ROBOT_API_ID_LOCO_SET_ARM_TASK = 7106

# R1 の FSM ID（G1 とは値が違うので G1 用の定数を流用しないこと）
FSM_ZERO_TORQUE = 0    # 脱力。バランス制御なし
FSM_DAMP = 1           # ダンピング。バランス制御なし（立位で送ると倒れる）
FSM_LOCKED_STAND = 4   # Locked Stand。バランス制御なし
FSM_LIE_TO_STAND = 701  # 仰向け → 起立（先に Locked Stand にしておく）
FSM_STAND_TO_LIE = 702  # 起立 → 仰向け
FSM_RUN = 811          # 歩行・走行制御（Running Mode）


class R1LocoClient(Client):
    """R1 の高レベル運動サービス（モード切替・速度指令・簡易ジェスチャー）。"""

    def __init__(self, service_name: str = LOCO_SERVICE_NAME):
        super().__init__(service_name, False)
        self._shake_hand_stage = -1

    def Init(self):
        self._SetApiVerson(LOCO_API_VERSION)
        self._RegistApi(ROBOT_API_ID_LOCO_GET_FSM_ID, 0)
        self._RegistApi(ROBOT_API_ID_LOCO_SET_FSM_ID, 0)
        self._RegistApi(ROBOT_API_ID_LOCO_SET_VELOCITY, 0)
        self._RegistApi(ROBOT_API_ID_LOCO_SET_ARM_TASK, 0)

    # --- 基本 API（戻り値 0 が成功）
    def GetFsmId(self):
        code, data = self._Call(ROBOT_API_ID_LOCO_GET_FSM_ID, "{}")
        if code != 0:
            return code, None
        return code, json.loads(data).get("data")

    def SetFsmId(self, fsm_id: int):
        code, _ = self._Call(ROBOT_API_ID_LOCO_SET_FSM_ID, json.dumps({"data": fsm_id}))
        return code

    def SetVelocity(self, vx: float, vy: float, omega: float, duration: float = 1.0):
        p = {"velocity": [vx, vy, omega], "duration": duration}
        code, _ = self._Call(ROBOT_API_ID_LOCO_SET_VELOCITY, json.dumps(p))
        return code

    def SetTaskId(self, task_id: int):
        code, _ = self._Call(ROBOT_API_ID_LOCO_SET_ARM_TASK, json.dumps({"data": task_id}))
        return code

    # --- モード切替
    def ZeroTorque(self):
        return self.SetFsmId(FSM_ZERO_TORQUE)

    def Damp(self):
        return self.SetFsmId(FSM_DAMP)

    def Stance(self):
        return self.SetFsmId(FSM_LOCKED_STAND)

    def Start(self):
        return self.SetFsmId(FSM_RUN)

    def Lie2StandUp(self):
        return self.SetFsmId(FSM_LIE_TO_STAND)

    def StandUp2Lie(self):
        return self.SetFsmId(FSM_STAND_TO_LIE)

    # --- 移動
    def Move(self, vx: float, vy: float, vyaw: float, continous_move: bool = False):
        """速度指令。既定では 1 秒で失効するので、歩き続けるには周期的に再送する。"""
        return self.SetVelocity(vx, vy, vyaw, 864000.0 if continous_move else 1.0)

    def StopMove(self):
        return self.SetVelocity(0.0, 0.0, 0.0)

    # --- 簡易ジェスチャー
    def WaveHand(self, turn_flag: bool = False):
        return self.SetTaskId(1 if turn_flag else 0)

    def ShakeHand(self, stage: int = -1):
        """stage=0 で手を出す、1 で戻す。省略時は呼ぶたびに交互。"""
        if stage == 0:
            self._shake_hand_stage = False
            return self.SetTaskId(2)
        if stage == 1:
            self._shake_hand_stage = True
            return self.SetTaskId(3)
        self._shake_hand_stage = not self._shake_hand_stage
        return self.SetTaskId(3 if self._shake_hand_stage else 2)


# ---------------------------------------------------------------- arm action
ARM_ACTION_SERVICE_NAME = "arm"
ARM_ACTION_API_VERSION = "1.0.0.0"

ROBOT_API_ID_ARM_ACTION_EXECUTE_ACTION = 7106
ROBOT_API_ID_ARM_ACTION_GET_ACTION_LIST = 7107
ROBOT_API_ID_ARM_ACTION_EXECUTE_CUSTOM_ACTION = 7108
ROBOT_API_ID_ARM_ACTION_STOP_CUSTOM_ACTION = 7113

# 公式マニュアル記載のプリセット。ファームウェアで変わるので GetActionList() の結果を優先する。
R1_ARM_ACTIONS = {
    "release_arm": 99,
    "blow_kiss_with_both_hands": 11,
    "blow_kiss_with_left_hand": 12,
    "blow_kiss_with_right_hand": 13,
    "both_hands_up": 15,
    "clamp": 17,  # 拍手
    "high_five": 18,
    "hug": 19,
    "refuse": 22,
    "right_hand_up": 23,
    "ultraman_ray": 24,
    "wave_under_head": 25,
    "wave_above_head": 26,
    "shake_hand": 27,
    "box_left_hand_win": 28,
    "box_right_hand_win": 29,
    "box_both_hand_win": 30,
    "extend_right_arm_forward": 31,
    "right_hand_on_heart": 33,
    "both_hands_up_deviate_right": 34,
    "emphasize": 35,
    "forward_push": 36,
}


class R1ArmActionClient(Client):
    """R1 の上半身プリセット動作サービス。

    ExecuteAction はブロッキング呼び出し（再生が終わるまで戻らない）なので、
    SetTimeout() は動作時間より長く（10 秒推奨）設定する。
    """

    def __init__(self):
        super().__init__(ARM_ACTION_SERVICE_NAME, False)

    def Init(self):
        self._SetApiVerson(ARM_ACTION_API_VERSION)
        self._RegistApi(ROBOT_API_ID_ARM_ACTION_EXECUTE_ACTION, 0)
        self._RegistApi(ROBOT_API_ID_ARM_ACTION_GET_ACTION_LIST, 0)
        self._RegistApi(ROBOT_API_ID_ARM_ACTION_EXECUTE_CUSTOM_ACTION, 0)
        self._RegistApi(ROBOT_API_ID_ARM_ACTION_STOP_CUSTOM_ACTION, 0)

    def ExecuteAction(self, action):
        """action は ID（int）または R1_ARM_ACTIONS の名前（str）。"""
        action_id = R1_ARM_ACTIONS[action] if isinstance(action, str) else int(action)
        code, _ = self._Call(ROBOT_API_ID_ARM_ACTION_EXECUTE_ACTION, json.dumps({"action_id": action_id}))
        return code

    def ReleaseArm(self):
        return self.ExecuteAction(R1_ARM_ACTIONS["release_arm"])

    def GetActionList(self):
        """(code, [プリセット一覧, カスタム一覧]) を返す。"""
        code, data = self._Call(ROBOT_API_ID_ARM_ACTION_GET_ACTION_LIST, "{}")
        if code != 0:
            return code, None
        return code, json.loads(data)

    def ExecuteCustomAction(self, action_name: str):
        """ティーチングで保存した動作を再生する（ノンブロッキング）。"""
        code, _ = self._Call(ROBOT_API_ID_ARM_ACTION_EXECUTE_CUSTOM_ACTION, json.dumps({"action_name": action_name}))
        return code

    def StopCustomAction(self):
        code, _ = self._Call(ROBOT_API_ID_ARM_ACTION_STOP_CUSTOM_ACTION, "{}")
        return code

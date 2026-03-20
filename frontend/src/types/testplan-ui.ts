export type UploadMode = 'ddlist' | 'inventory'

export interface EditDialogSubmitPayload {
  pn: string
  os_name: string
  fw_result?: string
  driver_result?: string
}

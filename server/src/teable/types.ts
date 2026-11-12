export interface TeableField { id: string; name: string; type: string; dbFieldName?: string; [k: string]: unknown }
export interface TeableTable { id: string; name: string; dbTableName: string; description?: string; icon?: string }
export interface TeableBase { id: string; name: string | null; spaceId: string; role?: string }
export interface TeableRecord { id: string; fields: Record<string, unknown> }

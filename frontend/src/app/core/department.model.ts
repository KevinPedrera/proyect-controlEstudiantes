export type DepartmentGroup = 'INSPECCION' | 'DECE' | 'SALUD';
export type Availability = 'DISPONIBLE' | 'NO_DISPONIBLE';

export interface Department {
  id: number;
  name: string;
  group: DepartmentGroup;
  active: boolean;
  availability: Availability;
}


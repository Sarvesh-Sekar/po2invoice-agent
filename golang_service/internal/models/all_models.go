package models

// AllModels returns every GORM model registered for database.AutoMigrate.
// The list mirrors the er2 shared schema plus the Go-owned auth table.
func AllModels() []any {
	return []any{
		&FieldDefinition{},
		&User{},
		&Customer{},
		&Product{},
		&PurchaseOrder{},
		&POLineItem{},
		&POHeaderField{},
		&POLineItemField{},
		&Invoice{},
		&Sale{},
		&EpisodicMemory{},
	}
}

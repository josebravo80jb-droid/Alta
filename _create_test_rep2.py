with open('tests/test_reportes.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('with TestClientapp, raise_server_exceptions=True) as c:', 'with TestClient(app, raise_server_exceptions=True) as c:')
text = text.replace('kpi_clinico, generX_reporte', 'kpi_clinico, generar_reporte')
text = text.replace('c_id = sepup_data["konsultorio"].id', 'c_id = setup_data["setup_data"].id if "setup_data" in setup_data else setup_data["setup_data"].id' if False else 'c_id = setup_data["onsultorio"].id')
text = text.replace('unsultorio", 'consultorio')

with open('tests/test_reportes.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Fixed test_reportes.py')

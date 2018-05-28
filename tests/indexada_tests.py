import unittest

from destral import testing
from destral.transaction import Transaction
from expects import *
from ..tarifes import *
import tools

HOLIDAYS = [
    # 2017
    date(2017, 1, 1),
    date(2017, 5, 1),
    date(2017, 8, 15),
    date(2017, 10, 12),
    date(2017, 11, 1),
    date(2017, 12, 6),
    date(2017, 12, 8),
    date(2017, 12, 25),
]

TARIFFS = {
    '2.0A': (Tarifa20A, Tarifa20APoolSOM),
    '2.0DHA': (Tarifa20DHA, Tarifa20DHAPoolSOM),
    '2.1A': (Tarifa21A, Tarifa21APoolSOM),
    '2.1DHA': (Tarifa21DHA, Tarifa21DHAPoolSOM),
    '3.0A': (Tarifa30A, Tarifa30APoolSOM),
    '3.1A': (Tarifa31A, Tarifa31APoolSOM),
    '3.1A LB': (Tarifa31ALB, Tarifa31ALBPoolSOM),
    '6.1A': (Tarifa61A, Tarifa61APoolSOM)
}


class IndexadaSOMTest(testing.OOTestCase):
    ''' Test indexed SOM tariffs '''
    def crear_modcon(self, cursor, uid, polissa_id, ini, fi):
        '''Creates a modcon in contract'''
        pool = self.openerp.pool
        polissa_obj = pool.get('giscedata.polissa')
        pol = polissa_obj.browse(cursor, uid, polissa_id)
        pol.send_signal(['modcontractual'])
        wz_crear_mc_obj = pool.get('giscedata.polissa.crear.contracte')

        ctx = {'active_id': polissa_id}
        params = {'duracio': 'nou'}

        wz_id_mod = wz_crear_mc_obj.create(cursor, uid, params, ctx)
        wiz_mod = wz_crear_mc_obj.browse(cursor, uid, wz_id_mod, ctx)
        res = wz_crear_mc_obj.onchange_duracio(
            cursor, uid, [wz_id_mod], wiz_mod.data_inici, wiz_mod.duracio,
            ctx
        )
        wiz_mod.write({
            'data_inici': ini,
            'data_final': fi
        })
        wiz_mod.action_crear_contracte(ctx)

    def get_curve(self):
        curve = []

        for day_num in range(1, 32):
            day = copy.copy([])
            for hour in range(0, 24):
                day.append(round(day_num * 1.0 + (hour / 100.0), 2))
            day.append(0.0)
            curve.append(day)
        return curve

    def test_facturador_get_tarifa_class(self):
        facturador_obj = self.openerp.pool.get(
            'giscedata.facturacio.facturador'
        )
        tarifa_obj = self.openerp.pool.get(
            'giscedata.polissa.tarifa'
        )

        with Transaction().start(self.database) as txn:
            cursor = txn.cursor
            uid = txn.user

            contract_obj = self.openerp.pool.get('giscedata.polissa')
            imd_obj = self.openerp.pool.get('ir.model.data')

            # gets contract 0001
            contract_id_index = imd_obj.get_object_reference(
                cursor, uid, 'giscedata_polissa', 'polissa_0001'
            )[1]

            contract_id_atr = imd_obj.get_object_reference(
                cursor, uid, 'giscedata_polissa', 'polissa_0002'
            )[1]

            # Test all available DSO access fare
            for tariff_name in TARIFFS:

                tariff_id = tarifa_obj.search(
                    cursor, uid, [('name', '=', tariff_name)]
                )[0]

                contract_obj.write(
                    cursor, uid, [contract_id_index, contract_id_atr],
                    {'tarifa': tariff_id}
                )

                contract_index = contract_obj.browse(
                    cursor, uid, contract_id_index
                )
                contract_atr = contract_obj.browse(
                    cursor, uid, contract_id_atr
                )

                tariff_class_index = facturador_obj.get_tarifa_class(
                    contract_index
                )
                tariff_class_atr = facturador_obj.get_tarifa_class(
                    contract_atr
                )

                expect(contract_atr.mode_facturacio).to(equal('atr'))
                expect(tariff_class_atr).to(be(TARIFFS[tariff_name][0]))

                expect(contract_index.mode_facturacio).to(equal('index'))
                expect(tariff_class_index).to(be(TARIFFS[tariff_name][1]))

    def test_facturador_versions_de_preus(self):
        facturador_obj = self.openerp.pool.get(
            'giscedata.facturacio.facturador'
        )
        self.openerp.install_module(
            'giscedata_tarifas_pagos_capacidad_20170101'
        )
        self.openerp.install_module(
            'giscedata_tarifas_peajes_20170101'
        )
        with Transaction().start(self.database) as txn:
            cursor = txn.cursor
            uid = txn.user

            contract_obj = self.openerp.pool.get('giscedata.polissa')
            imd_obj = self.openerp.pool.get('ir.model.data')

            # gets contract 0001
            contract_id_index = imd_obj.get_object_reference(
                cursor, uid, 'giscedata_polissa', 'polissa_0001'
            )[1]

            contract_id_atr = imd_obj.get_object_reference(
                cursor, uid, 'giscedata_polissa', 'polissa_0002'
            )[1]

            pricelist_id = imd_obj.get_object_reference(
                cursor, uid, 'giscedata_facturacio',
                'pricelist_tarifas_electricidad'
            )[1]

            contract_obj.send_signal(
                cursor, uid, [contract_id_index], ['validar', 'contracte']
            )
            self.crear_modcon(
                cursor, uid, contract_id_index, '2017-01-01', '2017-12-31'
            )

            contract_obj.send_signal(
                cursor, uid, [contract_id_atr], ['validar', 'contracte']
            )
            self.crear_modcon(
                cursor, uid, contract_id_atr, '2017-01-01', '2017-12-31'
            )

            context = {'llista_preu': pricelist_id}
            preus = facturador_obj.versions_de_preus(
                cursor, uid, contract_id_index, '2017-01-01', '2017-01-31',
                context
            )

            for version, productes in preus.items():
                expect(productes).to(have_key('k'))
                expect(productes).to(have_key('d'))
                expect(productes).to(have_key('fe'))
                expect(productes).to(have_key('imu'))
                expect(productes).to(have_key('omie'))
                expect(productes).to(have_key('pc'))
                expect(productes).to(have_key('fe'))
                expect(productes).to(have_key('atr'))

            preus = facturador_obj.versions_de_preus(
                cursor, uid, contract_id_atr, '2017-01-01', '2017-01-31',
                context
            )

            for version, productes in preus.items():
                expect(productes).to(be_an(int))
                expect(productes).to(equal(pricelist_id))

    def test_phf(self):
        ESIOS_TOKEN = tools.config['esios_token']
        token = ESIOS_TOKEN

        facturador_obj = self.openerp.pool.get(
            'giscedata.facturacio.facturador'
        )
        self.openerp.install_module(
            'giscedata_tarifas_pagos_capacidad_20170101'
        )
        self.openerp.install_module(
            'giscedata_tarifas_peajes_20170101'
        )
        with Transaction().start(self.database) as txn:
            cursor = txn.cursor
            uid = txn.user

            contract_obj = self.openerp.pool.get('giscedata.polissa')
            imd_obj = self.openerp.pool.get('ir.model.data')

            # gets contract 0001
            contract_id_index = imd_obj.get_object_reference(
                cursor, uid, 'giscedata_polissa', 'polissa_0001'
            )[1]

            contract_id_atr = imd_obj.get_object_reference(
                cursor, uid, 'giscedata_polissa', 'polissa_0002'
            )[1]

            pricelist_id = imd_obj.get_object_reference(
                cursor, uid, 'giscedata_facturacio',
                'pricelist_tarifas_electricidad'
            )[1]

            contract_obj.send_signal(
                cursor, uid, [contract_id_index], ['validar', 'contracte']
            )
            self.crear_modcon(
                cursor, uid, contract_id_index, '2017-01-01', '2017-12-31'
            )

            context = {'llista_preu': pricelist_id}
            versions = facturador_obj.versions_de_preus(
                cursor, uid, contract_id_index, '2017-01-01', '2017-01-31',
                context
            )


            curve_data = self.get_curve()
            curve = Curve(datetime(2017, 1, 1))
            curve.load(curve_data)

            consums = {
                'activa': {'2017-01-01': curve_data},
                'reactiva': {'P1': 2}
            }
            tarifa = Tarifa20APoolSOM(
                consums, {},
                '2017-01-01', '2017-01-31',
                facturacio=1, facturacio_potencia='icp',
                data_inici_periode='2017-01-01',
                data_final_periode='2017-01-31',
                potencies_contractades={'P1': 4.6},
                versions=versions,
                holidays=HOLIDAYS,
                esios_token=token,
                audit=['pmd', 'curve', 'pc3_ree']
            )

            component = tarifa.phf_calc(
                curve, date(2017, 1, 1)
            )
            # test component
            tarifa.factura_energia()
            assert tarifa.code == '2.0A'
            activa = tarifa.termes['activa']

            # CURVE
            curve_audit = tarifa.get_audit_data('curve')
            tarifa.dump_audit_data('curve', '/tmp/curve_data.csv')
            # test
            expect(curve_audit[0]).to(
                equal(("2017-01-01 01", 0.001, '', ''))
            )
            expect(curve_audit[-1]).to(
                equal(("2017-01-31 24", 0.03123, '', ''))
            )
            with open('/tmp/curve_data.csv', 'r') as curvefile:
                first_line = curvefile.readline()
            expect(first_line).to(equal('2017-01-01 01;0.001;;\r\n'))

            # PMD
            pmd_audit = tarifa.get_audit_data('pmd')
            tarifa.dump_audit_data('pmd', '/tmp/pmd_data.csv')
            # test
            prmncur = Prmncur("C2_prmncur_20170101_20170131")
            expect(pmd_audit[0]).to(
                equal(
                    ("2017-01-01 01",
                     prmncur.get(1, 0),
                     prmncur.file_version,
                     ''
                     )
                )
            )
            expect(pmd_audit[-1]).to(
                equal(
                    ("2017-01-31 24",
                     prmncur.get(31, 23),
                     prmncur.file_version,
                     ''
                     )
                )
            )
            with open('/tmp/pmd_data.csv', 'r') as curvefile:
                first_line = curvefile.readline()
            expect(first_line).to(
                equal('2017-01-01 01;{0};{1};\r\n'.format(
                    prmncur.get(1, 0), prmncur.file_version)
                )
            )

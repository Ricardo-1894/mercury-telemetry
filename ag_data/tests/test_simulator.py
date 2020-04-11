from random import randint, uniform

from django.test import TestCase
from django.utils import timezone

from ag_data.simulator import Simulator
from ag_data.models import AGMeasurement
from ag_data.presets import helpers as preset_helpers
from ag_data.presets import sample_user_data
from ag_data import utilities


class SimulatorEmptyInitTest(TestCase):
    def setUp(self):
        self.sim = Simulator()

        self.assertEqual(self.sim.event, None)
        self.assertEqual(self.sim.sensor, None)

    def test_simulator_log_single_measurement_no_event(self):
        with self.assertRaises(AssertionError) as ae:
            timestamp = timezone.now()
            self.sim.logSingleMeasurement(timestamp=timestamp)
        correct_assertion_message = "Missing an instance of AGEvent."
        self.assertEqual(str(ae.exception), correct_assertion_message)

    def test_simulator_log_single_measurement_no_sensor(self):
        testVenue = preset_helpers.createVenueFromPresetAtIndex(0)
        self.sim.event = preset_helpers.createEventFromPresetAtIndex(testVenue, 0)

        with self.assertRaises(AssertionError) as ae:
            timestamp = timezone.now()
            self.sim.logSingleMeasurement(timestamp=timestamp)
        correct_assertion_message = "Missing an instance of AGSensor."
        self.assertEqual(str(ae.exception), correct_assertion_message)


class SimulatorTest(TestCase):
    def setUp(self):
        self.sim = Simulator()

        self.assertEqual(self.sim.event, None)
        self.assertEqual(self.sim.sensor, None)

        venue = preset_helpers.createVenueFromPresetAtIndex(self.randVenueIndex())
        self.event = preset_helpers.createEventFromPresetAtIndex(
            venue, self.randEventIndex()
        )

        utilities.createOrResetAllBuiltInSensorTypes()
        self.sensor = preset_helpers.createSensorFromPresetAtIndex(
            self.randSensorIndex()
        )

        self.sim.setUp(self.event, self.sensor)

    def test_simulator_log_single_measurement(self):

        timestamp = timezone.now()
        measurement = self.sim.logSingleMeasurement(timestamp=timestamp)

        # test data in database
        measurement_in_database = AGMeasurement.objects.get(pk=measurement.uuid)
        self.assertEqual(measurement_in_database.timestamp, timestamp)
        self.assertEqual(measurement_in_database.event_uuid, self.sim.event)
        self.assertEqual(measurement_in_database.sensor_id, self.sim.sensor)

        # test measurement payload format by cross comparison of all keys in payload
        # and the expected specification
        measurement_payload = measurement_in_database.value
        correct_payload_format = self.sim.sensor.type_id.format

        self.crossCompareKeys(
            correct_payload_format["reading"], measurement_payload["reading"]
        )
        self.crossCompareKeys(
            correct_payload_format["result"], measurement_payload["result"]
        )

        # FIXME: test measurement value field data type (string/float/bool/...)

    def test_simulator_log_single_measurement_all_sensor_samples(self):
        # FIXME: add tests for all built-in sensor types and supported sample sensors
        return

    def test_simulator_log_multiple_measurements(self):
        import sys
        from io import StringIO

        randFrequencyInHz = uniform(1, 100)
        randSeconds = uniform(1, 60)

        self.sim.logMeasurementsInThePastSeconds(
            seconds=randSeconds, frequencyInHz=randFrequencyInHz, printProgress=False
        )

        # test number of measurements
        totalMeasurementsInDatabase = (
            AGMeasurement.objects.filter(event_uuid=self.sim.event)
            .filter(sensor_id=self.sim.sensor)
            .count()
        )
        self.assertEqual(
            totalMeasurementsInDatabase, int(randSeconds * randFrequencyInHz)
        )

        # test output prompts
        saved_stdout = sys.stdout
        try:
            out = StringIO()
            sys.stdout = out

            self.sim.logMeasurementsInThePastSeconds(
                seconds=randSeconds, frequencyInHz=randFrequencyInHz
            )
            outputString = out.getvalue().strip()
            self.assertIn("({}% done!) Created ".format(100), outputString)
            self.assertIn(str(totalMeasurementsInDatabase), outputString)
        finally:
            sys.stdout = saved_stdout

    def test_simulator_log_continuous_measurements(self):
        """Tests the logLiveMeasurements(self, frequencyInHz, sleepTimer) method in the
        Simulator class. By default, it will run the test 10 times.

        To run this test case only, and to stop testing when any failure is encountered,
        use this single command:

        python manage.py test ag_data.tests.test_simulator.SimulatorTest.
        test_simulator_log_continuous_measurements --failfast
        """

        # Change the number of loops for testing on demand
        for i in range(1):
            randFrequencyInHz = uniform(1, 100)
            randSleepTimer = uniform(1, 15)

            startTime = timezone.now()

            self.sim.logLiveMeasurements(
                frequencyInHz=randFrequencyInHz, sleepTimer=randSleepTimer
            )

            endTime = timezone.now()
            secondsElapsed = endTime - startTime

            # test sleep timer
            self.assertTrue(
                randSleepTimer - 1 <= secondsElapsed.seconds <= randSleepTimer + 1
            )

            # test total measurement count
            totalMeasurementsInDatabase = (
                AGMeasurement.objects.filter(event_uuid=self.sim.event)
                .filter(sensor_id=self.sim.sensor)
                .count()
            )

            expectedTotal = int(randSleepTimer * randFrequencyInHz)

            # If this test fails on a device, uncomment following lines for more info.

            # print("Actual: " + str(totalMeasurementsInDatabase))
            # print("Expected: " + str(expectedTotal))
            # print(
            #     "Completion: {:3.1f}%".format(
            #         totalMeasurementsInDatabase / expectedTotal * 100
            #     )
            # )

            self.assertTrue(
                expectedTotal * 0.7
                <= totalMeasurementsInDatabase
                <= expectedTotal * 1.1
            )

    def randVenueIndex(self):
        return randint(0, len(sample_user_data.sample_venues) - 1)

    def randEventIndex(self):
        return randint(0, len(sample_user_data.sample_events) - 1)

    def randSensorIndex(self):
        return randint(0, len(sample_user_data.sample_sensors) - 1)

    def crossCompareKeys(self, dictionary1, dictionary2):
        for field in dictionary1.keys():
            self.assertIn(field, dictionary2.keys())
        for field in dictionary2.keys():
            self.assertIn(field, dictionary1.keys())
